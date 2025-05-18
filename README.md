# ninox

Ninox generates alt text for images using OpenAI's Responses API.

## Requirements

* **Python 3.13+**
* Project dependencies from `pyproject.toml`

Install everything in editable mode:

```bash
pip install -e .
```

## Configuration

Create `~/.config/ninox/config.toml` with your API token:

```toml
[tokens.openai]
open = "sk-your-openai-token"
closed = ""
```

## Usage

Run `ninox` to annotate images in a directory:

```bash
ninox describe-images /path/to/images -c "Short context for the batch"
```

The command adds `.meta` sidecar files next to each image containing the generated description.
