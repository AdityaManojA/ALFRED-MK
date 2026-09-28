# File & Folder Exploration Workflow

This workflow guides Alfred when performing native file launches, folder exploration, and storing findings into the dedicated Intel Terminal.

## Step 1: Target Identification
- If the user provides a path, resolve it against:
  - System drives: `C:\`, `D:\`, etc.
  - Standard folders: `desktop`, `downloads`, `documents`, `home`.
  - Current Mark-LIV repository.
- If only a filename is given, first run `file_controller` with `action: "find"` to locate the file, or search standard user locations.

## Step 2: Open File vs Explore Folder
- **Open File**:
  - `file_controller(action="open", path="<path_or_filename>")`
  - Launches with default registered OS association.
- **Explore Folder**:
  - `file_controller(action="explore", path="<folder_or_file>")`
  - Opens Windows File Explorer at the folder or highlights the target item.

## Step 3: Record Intel or Links
- When research, URLs, documentation paths, or notes are derived during the process:
  - Call `intel_notes(title="<title>", content="<content_or_url>", note_type="link"|"note"|"data")`
  - This populates the user's dedicated Intel Terminal directly without cluttering the chat screen.
