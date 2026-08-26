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
# rewrites url/sha256 on each corpora-py release tag (version is inferred
# from the tag URL — an explicit stanza fails `brew audit` as redundant).
class Corpora < Formula
  include Language::Python::Virtualenv

  desc "Convert documents into queryable .corpus text archives"
  homepage "https://github.com/exegia/corpora-py"
  url "https://github.com/exegia/corpora-py/archive/refs/tags/v2.2.0.tar.gz"
  sha256 "e2153ef80aaa2933ee4e2d59065d88edf17044a53caf08f90469c3aa3a3dc366"
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

  # Homebrew's post-install processing leaves many of the pip-installed
  # native extensions (lxml, pdf-inspector, hf_xet, ...) with invalid ad-hoc
  # code signatures; on Apple Silicon the kernel then SIGKILLs the process
  # with "Code Signature Invalid" the moment such a page is executed. Re-sign
  # every Mach-O in the virtualenv after everything else has touched it —
  # post_install runs last (and on `brew postinstall corpora` for an
  # already-broken keg).
  def post_install
    Dir[libexec/"lib/**/*.so", libexec/"lib/**/*.dylib"].each do |f|
      system "codesign", "--force", "--sign", "-", f
    end
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
