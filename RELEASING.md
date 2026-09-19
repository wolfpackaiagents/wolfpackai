# Releasing Wolfpack AI

## Framework release

1. Confirm that `main` is green and the version is ready to publish.
2. Run the `Publish to PyPI` GitHub Actions workflow from `main`.
3. Enter a version tag in the format requested by the workflow.
4. Verify the package on PyPI (Python Package Index), the Git tag, and the generated release commit.

The workflow runs tests, builds the package, publishes it, commits release metadata, and creates the tag.

## Control plane and website release

Changes merged into `main` can publish Docker images and deploy the website through GitHub Actions. Verify the associated workflow results after merging.

## Security release

For a security fix, keep the vulnerability private until a patched release is available. Follow [SECURITY.md](SECURITY.md).
