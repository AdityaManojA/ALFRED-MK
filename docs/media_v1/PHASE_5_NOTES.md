# Media Command v1 — Phase 5: Image Sources

- Added `ImageSource` and the privacy-safe `ImageResult` contract.
- `LocalSource` lazily indexes Pictures, Downloads, and Desktop no more than once per 300 seconds; explicit existing paths bypass the index.
- `WebSource` queries Openverse only, with a six-second timeout and eight-result cap. It does not log or persist search text.
- Web result attribution and licence are retained for the image-deck caption.
