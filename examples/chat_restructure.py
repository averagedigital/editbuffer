from editbuffer import EditBuffer, Selection

buffer = EditBuffer("Summary: The build failed.\nDetails: timeout\nNext: retry")
buffer.replace(
    Selection.context(before="Details: ", text="timeout", after="\nNext:"),
    "integration tests timed out after 10 minutes",
)
buffer.insert_before(Selection.exact("Next:"), "Impact: release blocked\n")

print(buffer.commit())
