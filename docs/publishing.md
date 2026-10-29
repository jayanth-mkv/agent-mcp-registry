# Independent PyPI releases

Each standalone MCP is a separate Python distribution. Publishing is performed by [publish.yml](../.github/workflows/publish.yml) through GitHub Actions and PyPI Trusted Publishing. No PyPI token is stored in GitHub or used locally.

## Published packages

Version **0.2.0** of both packages is published on PyPI: [mcp-files-context](https://pypi.org/project/mcp-files-context/0.2.0/) and [mcp-email-validator](https://pypi.org/project/mcp-email-validator/0.2.0/). Both were installed from public PyPI in isolation and verified through stdio MCP sessions and tool calls.

The file server's distribution is named `mcp-files-context` because PyPI rejected `mcp-files` as too similar to an existing project; its console command and source directory remain `mcp-files`. The email distribution and command are both `mcp-email-validator`.

## Connect PyPI once

Sign in to your PyPI account and open [account publishing settings](https://pypi.org/manage/account/publishing/). Add a **pending publisher** for each package:

| PyPI form field | File Server | Email Validator |
| --- | --- | --- |
| PyPI project name | `mcp-files-context` | `mcp-email-validator` |
| Owner | `jayanth-mkv` | `jayanth-mkv` |
| Repository name | `agent-mcp-registry` | `agent-mcp-registry` |
| Workflow filename | `publish.yml` | `publish.yml` |
| Environment name | `pypi-files` | `pypi` |

The workflow filename has no directory prefix. The environment name must match exactly. PyPI creates each project on its first successful trusted publication; a pending publisher does not reserve a name. See [PyPI's setup instructions](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

The two pending publishers must have distinct configurations so PyPI can identify which project to create. Keep the same repository and workflow, and use the different environment names above. See [PyPI's explanation of multiple projects per repository](https://docs.pypi.org/trusted-publishers/internals/).

The GitHub repository's `pypi-files` environment permits only `mcp-files-v*` tags; `pypi` permits only `mcp-email-validator-v*` tags. Only the publishing job receives `id-token: write`. Build and test jobs have read-only repository access and no publishing identity. No mandatory human approval has been added to either environment.

## Validate without publishing

In GitHub, open **Actions → Publish MCP package → Run workflow**, choose a package, and run it on `main`. Every manual run is validation-only, even when started on a tag. It tests on Linux and Windows, builds wheel and source distributions, checks their metadata, installs the wheel in isolation, and retains verified Linux artifacts for seven days.

The [MCP package checks](../.github/workflows/ci.yml) workflow also tests both packages on Linux and Windows for changes to their source or workflow files. It runs release-guard regression tests as well.

## Publish one package

1. Set the selected package's version in its `pyproject.toml` and server version metadata. Refresh its lockfile with `uv lock --project <package>` and update versioned usage examples.
2. Commit and push those changes to `main`. Wait for passing package checks.
3. Confirm the package's PyPI Trusted Publisher is registered.
4. Create and push an annotated tag for that package. For the current File Server version:

```bash
git tag -a mcp-files-v0.2.0 -m "Release mcp-files 0.2.0"
git push origin mcp-files-v0.2.0
```

To release only Email Validator instead:

```bash
git tag -a mcp-email-validator-v0.2.0 -m "Release mcp-email-validator 0.2.0"
git push origin mcp-email-validator-v0.2.0
```

Each tag publishes only its named package. The workflow rejects tags whose version differs from the package manifest or whose commit is not an ancestor of `main`. Both Linux and Windows checks must pass before the publishing job starts. That job downloads the already verified Linux distributions and publishes them without rebuilding, using OIDC and package attestations.

Experimental examples are excluded. Plain version tags such as `v0.2.0`, ordinary branch pushes, and manual workflow runs do not publish.

## User commands

Users can run just the MCP they need without Git or a checkout:

```bash
uvx --python 3.13 --from mcp-files-context==0.2.0 mcp-files --workspace ./workspace
```

```bash
uvx --python 3.13 mcp-email-validator@0.2.0
```

For MCP clients supporting `mcpServers`, copy only the entry you need:

```json
{
  "mcpServers": {
    "files": {
      "command": "uvx",
      "args": ["--python", "3.13", "--from", "mcp-files-context==0.2.0", "mcp-files", "--workspace", "/absolute/path/allowed-files"]
    },
    "email-validator": {
      "command": "uvx",
      "args": ["--python", "3.13", "mcp-email-validator@0.2.0"]
    }
  }
}
```

## Failed or partial publications

Inspect the Actions log first. A missing or mismatched Trusted Publisher must be corrected in PyPI before rerunning the failed publishing job. PyPI distribution files cannot be overwritten. If a partial upload has already registered a version, inspect which files exist and release a new version when necessary; do not delete or move the release tag to hide the failed attempt. The workflow deliberately does not skip existing distributions or fall back to a token.
