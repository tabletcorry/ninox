# ninox

Ninox is intended to be a catch-all tool for various LLM scripts I make.

Currently has the following:
* `describe-images`: generates alt text for images using OpenAI's Responses API.
* `generate-menu-tree`: mirrors menu PDFs from S3 into a Hugo content tree.
* `git commit`: suggests a commit message for staged changes.

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

### generate-menu-tree

Mirror menu PDFs from S3 and create a Hugo content structure:

```bash
ninox generate-menu-tree --bucket my-bucket --cdn-host https://cdn.example.com
```

The command creates `content/hal_menus/...` directories with daily `index.md` files linking to the PDFs via the provided CDN host.
Any leading 32-character MD5 hashes in the filenames are stripped from the link display names.

### git commit

Generate a commit message for staged changes:

```bash
ninox git commit
```

Pass `--model` to choose an alternate OpenAI model.
