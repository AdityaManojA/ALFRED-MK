"""
Local audio pipeline coordinator for MARK XL.
Handles STT → LLM → TTS flow for offline operation.
"""

import asyncio
import threading
import queue
import time
from typing import Optional, Callable, Dict, Any
import numpy as np

from core.local_stt import LocalSTTManager, create_local_stt_engine
from core.local_ttt import LocalTTSManager, create_local_tts_engine
from core.llm_client import (
    call_llm_stream, call_llm_text, get_llm_provider,
    get_llm_settings, ensure_ollama_running
)
from core.echo import EchoGuard


class LocalLLMManager:
    """Manages local LLM interactions."""

    def __init__(self, config: dict):
        self.config = config
        self.provider = get_llm_provider()
        self.url, self.model = get_llm_settings()
        self.system_prompt = ""  # Will be set from JarvisLive
        self.tools = []  # Will be set from JarvisLive
        self.history = []  # Conversation history

        # Warm up the model
        if self.provider == "ollama":
            ensure_ollama_running()

    def set_context(self, system_prompt: str, tools: list):
        """Set system prompt and available tools."""
        self.system_prompt = system_prompt
        self.tools = tools

    def add_to_history(self, role: str, content: str):
        """Add message to conversation history."""
        self.history.append({"role": role, "content": content})
        # Keep history reasonable size
        if len(self.history) > 20:
            self.history = self.history[-20:]

    def clear_history(self):
        """Clear conversation history."""
        self.history = []

    async def generate_response(
        self,
        prompt: str,
        stream_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        """Generate response from local LLM."""
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        messages.extend(self.history)
        messages.append({"role": "user", "content": prompt})

        full_response = ""

        try:
            if stream_callback:
                # Streaming response
                for chunk in call_llm_stream(messages, tools=self.tools):
                    if chunk.get("type") == "sentence":
                        text = chunk.get("text", "")
                        if text:
                            full_response += text
                            stream_callback(text)
                    elif chunk.get("type") == "done":
                        full_response = chunk.get("content", "")
                        # Handle tool calls if present
                        tool_calls = chunk.get("tool_calls", [])
                        if tool_calls:
                            # Process tool calls and get final response
                            return await self._handle_tool_calls(
                                tool_calls, full_response, stream_callback
                            )
                        break
            else:
                # Non-streaming response
                result = call_llm(messages, tools=self.tools)
                full_response = result.get("content", "")
                tool_calls = result.get("tool_calls", [])
                if tool_calls:
                    return await self._handle_tool_calls(
                        tool_calls, full_response, stream_callback
                    )

            # Add to history
            self.add_to_history("assistant", full_response)
            return full_response

        except Exception as e:
            print(f"[LocalLLM] Generation error: {e}")
            return f"Error generating response: {str(e)}"

    async def _handle_tool_calls(
        self,
        tool_calls: list,
        initial_response: str,
        stream_callback: Optional[Callable[[str], None]]
    ) -> str:
        """Handle tool calls by executing them and getting final response."""
        # This would integrate with JarvisLive's _dispatch_tool
        # For now, we'll return a placeholder - actual implementation
        # would need access to JarvisLive instance
        tool_results = []
        for tc in tool_calls:
            tool_name = tc.get("function", {}).get("name", "")
            tool_args = tc.get("function", {}).get("arguments", {})
            # In real implementation, this would call JarvisLive._dispatch_tool
            tool_results.append({
                "tool": tool_name,
                "result": f"Tool {tool_name} executed"  # Placeholder
            })

        # Create follow-up prompt with tool results
        follow_up = f"{initial_response}\n\nTool results: {tool_results}\n\nPlease provide a final response based on this information."
        return await self.generate_response(follow_up, stream_callback)


class LocalPipelineCoordinator:
    """Coordinates STT → LLM → TTS flow."""

    def __init__(self, config: dict, ui_interface):
        self.config = config
        self.ui = ui_interface
        self._loop = None

        # Initialize components
        self.stt_manager = create_local_stt_engine(config)
        self.tts_manager = create_local_tts_engine(config)
        self.llm_manager = LocalLLMManager(config)

        # Queues for inter-component communication
        self.audio_queue = queue.Queue()

        # State flags
        self.is_running = False
        self.is_listening = False
        self.is_processing = False
        self.is_speaking = False
        self._wake_enabled = False
        self._awake = False

        # Echo guard for barge-in detection
        self.echo_guard = EchoGuard()

        # Callbacks from UI/JarvisLive
        self._on_state_change = None
        self._on_log_message = None
        self._on_wake_word_detected = None

        # Set up STT audio callback
        self.stt_manager.set_audio_callback(self._audio_callback)

    def set_ui_callbacks(
        self,
        on_state_change: Optional[Callable[[str], None]] = None,
        on_log_message: Optional[Callable[[str], None]] = None,
        on_wake_word_detected: Optional[Callable[[], None]] = None
    ):
        """Set callbacks for UI updates."""
        self._on_state_change = on_state_change
        self._on_log_message = on_log_message
        self._on_wake_word_detected = on_wake_word_detected

        # Also set up LLM context if we have access to UI methods
        if hasattr(self.ui, '_build_system_instruction'):
            # This will be called later when we have the full system instruction
            pass

    def _log(self, message: str):
        """Log message via callback or print."""
        if self._on_log_message:
            self._on_log_message(message)
        else:
            print(f"[LocalPipeline] {message}")

    def _set_state(self, state: str):
        """Set UI state via callback."""
        if self._on_state_change:
            self._on_state_change(state)
        # Also try to call UI directly if available
        if hasattr(self.ui, 'set_state'):
            try:
                self.ui.set_state(state)
            except Exception:
                pass

    def start(self):
        """Start the local pipeline."""
        if self.is_running:
            return

        self._log("Starting local audio pipeline...")
        self.is_running = True

        # Start STT listening
        self.stt_manager.start_listening()
        self.is_listening = True

        # Start processing loop
        self._processing_task = asyncio.create_task(self._processing_loop())

        self._log("Local audio pipeline started")

    def stop(self):
        """Stop the local pipeline."""
        if not self.is_running:
            return

        self._log("Stopping local audio pipeline...")
        self.is_running = False

        # Stop components
        self.stt_manager.stop_listening()
        self.is_listening = False

        self.tts_manager.stop()
        self.is_speaking = False

        if hasattr(self, '_processing_task'):
            self._processing_task.cancel()

        self._log("Local audio pipeline stopped")

    def _audio_callback(self, audio_bytes: bytes):
        """Callback for audio from STT manager."""
        if self.is_running and not self.is_speaking:
            self.audio_queue.put(audio_bytes)

    async def _processing_loop(self):
        """Main processing loop: STT → LLM → TTS."""
        audio_buffer = bytearray()
        silence_counter = 0
        max_silence_chunks = self.config.get("stt_min_silence_chunks", 10)

        while self.is_running:
            try:
                # Get audio chunk with timeout
                try:
                    audio_bytes = self.audio_queue.get(timeout=0.1)
                except queue.Empty:
                    # Timeout - check if we should process buffered audio
                    if (len(audio_buffer) > 0 and
                        silence_counter >= max_silence_chunks):
                        await self._process_utterance(bytes(audio_buffer))
                        audio_buffer = bytearray()
                        silence_counter = 0
                    continue

                if not self.is_speaking:  # Don't process while speaking (barge-in protection)
                    audio_buffer.extend(audio_bytes)

                    # Simple voice activity detection (energy-based)
                    audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32)
                    energy = np.sqrt(np.mean(audio_np ** 2))

                    if energy < 0.01:  # Silence threshold
                        silence_counter += 1
                    else:
                        silence_counter = 0

                    # If we have enough silence after speech, process utterance
                    if (silence_counter > max_silence_chunks and
                        len(audio_buffer) > self.stt_manager.sample_rate * 0.5):  # Minimum 0.5 seconds
                        await self._process_utterance(bytes(audio_buffer))
                        audio_buffer = bytearray()
                        silence_counter = 0

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._log(f"Processing loop error: {e}")
                await asyncio.sleep(0.1)

    async def _process_utterance(self, audio_bytes: bytes):
        """Process a complete utterance: transcribe → generate response → synthesize."""
        if self.is_processing:
            return

        self.is_processing = True
        try:
            self._log("Processing utterance...")

            # Transcribe audio
            if self.stt_manager.config.get("stt_engine", "whisper").lower() == "vosk":
                # For Vosk, we need to process the accumulated buffer differently
                # This is simplified - in practice we'd use the streaming results
                transcript = ""  # Placeholder - actual implementation would use Vosk streaming
            else:
                # For Whisper, transcribe the accumulated buffer
                audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
                transcript = self.stt_manager.stt.transcribe(audio_np)

            if not transcript or not transcript.strip():
                self._log("Empty transcription, skipping")
                return

            transcript = transcript.strip()
            self._log(f"You: {transcript}")

            # Update UI with user message
            if hasattr(self.ui, 'write_log'):
                self.ui.write_log(f"You: {transcript}")

            # Generate LLM response
            def stream_callback(text):
                if text:
                    # Update UI with assistant response (overwriting for streaming effect)
                    if hasattr(self.ui, 'write_log'):
                        self.ui.write_log(f"ALFRED: {text}", overwrite=True)
                    # Queue text for TTS
                    self.tts_manager.speak_sentence(text)

            # Generate response from LLM
            response = await self.llm_manager.generate_response(transcript, stream_callback)

            # Flush any remaining text for TTS
            self.tts_manager.flush()

            self._log(f"ALFRED: {response}")

        except Exception as e:
            self._log(f"Utterance processing error: {e}")
            if hasattr(self.ui, 'write_log'):
                self.ui.write_log(f"Error: {str(e)}")
        finally:
            self.is_processing = False

    def handle_wake_word(self):
        """Handle wake word detection."""
        if not self._wake_enabled:
            return

        if not self._awake:
            self._awake = True
            self._log("Wake word detected - waking up")
            if hasattr(self.ui, 'write_log'):
                self.ui.write_log("SYS: Awake — wake word.")
            self._set_state("LISTENING")

            if self._on_wake_word_detected:
                self._on_wake_word_detected()

    def handle_speech_end(self):
        """Handle end of speech detection."""
        # This would be called when we detect the user has finished speaking
        # In our implementation, this is handled in the processing loop
        pass

    def interrupt(self):
        """Handle barge-in/interruption."""
        self._log("Interruption detected")
        self.is_speaking = False

        # Clear audio queue
        try:
            while not self.audio_queue.empty():
                self.audio_queue.get_nowait()
        except queue.Empty:
            pass

        # Stop TTS
        self.tts_manager.stop()

        # Reset state
        self._set_state("LISTENING" if self._wake_enabled and not self._ui_muted() else "SLEEPING")

    def _ui_muted(self) -> bool:
        """Check if UI is muted."""
        if hasattr(self.ui, 'muted'):
            return self.ui.muted
        return False

    def set_wake_word_enabled(self, enabled: bool):
        """Enable or disable wake word detection."""
        self._wake_enabled = enabled
        if not enabled and self._awake:
            self._awake = False
            self._set_state("SLEEPING")

    def wake(self, reason: str = "wake word"):
        """Wake the assistant."""
        if not self._awake:
            self._awake = True
            self._log(f"Waking up due to: {reason}")
            if hasattr(self.ui, 'write_log'):
                self.ui.write_log(f"SYS: Awake — {reason}.")
            self._set_state("LISTENING")

    def sleep(self, reason: str = "timeout"):
        """Put the assistant to sleep."""
        if self._awake:
            self._awake = False
            self._log(f"Going to sleep due to: {reason}")
            if hasattr(self.ui, 'write_log'):
                self.ui.write_log(f"SYS: Sleeping — {reason}.")
            self._set_state("SLEEPING")


# Factory function for easy instantiation
def create_local_pipeline(config: dict, ui_interface) -> LocalPipelineCoordinator:
    """Create and configure a local pipeline coordinator."""
    return LocalPipelineCoordinator(config, ui_interface)