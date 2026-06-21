from editbuffer import EditBuffer, Selection
from editbuffer.validators import valid_shell

buffer = EditBuffer(validators=(valid_shell,))
buffer.append('find . -name "*.py" -exec grep -n "TODO" {} ;')
buffer.replace(Selection.exact("{} ;"), "{} \\;")

print(buffer.commit())
