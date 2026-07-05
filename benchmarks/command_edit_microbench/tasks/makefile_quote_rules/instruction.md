Create `/app/Makefile` and `/app/build_message.py`.

Use shell commands to write both files. The Makefile must have a target
`render` that runs the Python script and writes `/app/out/message.txt`.

The script must create the output directory and write exactly:

`status="ok"; path='C:\tmp\agent'; note=heredoc-ready`
