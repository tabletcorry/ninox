# ninox

Ninox is intended to be a catch-all tool for various LLM scripts I make.

Currently has the following:
* `describe-images`: generates alt text for images using OpenAI's Responses API.

## Requirements

* **Python 3.13+**
* Project dependencies from `pyproject.toml`

Install everything in editable mode:

```bash
uv tool install --editable .
```

## Configuration

Create `~/.config/ninox/config.toml` with your API token:

```toml
[tokens.openai]
open = "sk-your-openai-token"
closed = ""
```

Open/Closed aren't used yet, but are intended to indicate if data sharing is appropriate. Only open is used so far.

## Usage

### describe-images

Annotate images in a directory:

```bash
ninox describe-images /path/to/images
```

The command adds `.meta` sidecar files next to each image containing the generated description.
