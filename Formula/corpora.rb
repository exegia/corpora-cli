# corpora — terminal conversion CLI from exegia/corpora-py (issue #188).
#
# The formula installs the corpora-py distribution into its own virtualenv
# with pip resolving the (many) Python dependencies from PyPI, rather than
# vendoring every dependency as a Homebrew resource stanza — this is a
# personal tap, and the dependency closure (text-fabric, context-fabric,
# lxml, fastapi, ...) would be unmaintainable as resources.
#
# `url` points at the corpora-py source tarball; pip builds the same
# self-contained wheel the PyPI release ships (the root pyproject bundles
# all workspace packages). The bump workflow (.github/workflows/bump.yml)
# rewrites url/sha256/version on each corpora-py release tag.
class Corpora < Formula
  include Language::Python::Virtualenv

  desc "Convert documents into queryable .corpus text archives"
  homepage "https://github.com/exegia/corpora-py"
  url "https://github.com/exegia/corpora-py/archive/ceca6cb9a0ed061a692851405b797a92e548e3e4.tar.gz"
  version "2.0.0-dev"
  sha256 "64b137c7c2c69fc6001b3951ab688d4db7579d5c509fc018430db72d8647d786"
  license "MIT"

  depends_on "python@3.13"

  def install
    virtualenv_create(libexec, "python3.13")
    # Resolve third-party deps from PyPI; buildpath is the corpora-py
    # source tree itself.
    system libexec/"bin/python", "-m", "pip", "install", buildpath.to_s
    bin.install_symlink libexec/"bin/corpora"
    bin.install_symlink libexec/"bin/corpora-api"
    bin.install_symlink libexec/"bin/cf-mcp"
  end

  test do
    (testpath/"sample.txt").write <<~TEXT
      Sample Title

      Chapter 1

      Hello world this is a paragraph of test content for the formula.

      Another paragraph with more words to convert into an archive.
    TEXT
    system bin/"corpora", "convert", "sample.txt", "-o", "sample.corpus"
    assert_path_exists testpath/"sample.corpus"
    system bin/"corpora", "validate", "sample.corpus"
  end
end
