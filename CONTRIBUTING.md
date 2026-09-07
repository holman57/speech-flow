# Contributing to Speech Flow

Thank you for contributing to Speech Flow!

## Core Directives
- Keep client-side audio processing lightweight and dependency-free using standard Web Audio API and Web Speech API standards.
- Ensure all bidirectional IPC messages to Adrastea adhere to structured JSON contracts over TCP.
- Validate cross-browser compatibility across Chrome, Safari (macOS/iOS), and Edge.

## Submitting Pull Requests
1. Fork the repo and branch from `main`.
2. Test changes locally (`python -m speech_flow.cli test`).
3. Open a Pull Request with a clear description of the audio or UI improvements.
