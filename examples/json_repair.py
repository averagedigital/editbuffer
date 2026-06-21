from editbuffer import EditBuffer, Selection
from editbuffer.validators import valid_json

buffer = EditBuffer('{"model": "small", "temperature": 1}')
buffer.replace(Selection.exact('"small"'), '"large"')
buffer.replace(Selection.exact("1"), "0.2")

valid_json(buffer.view())
print(buffer.commit())
