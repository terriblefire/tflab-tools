# Vendored eagle2svg

The `tflab._eagle2svg` package is a vendored copy of a patched fork of
[eagle2svg](https://github.com/at-wat/eagle2svg) v0.1.5 by Atsushi Watanabe
<atsushi.w@ieee.org>, distributed under the BSD license (see upstream).

The patches (Bus rendering, Plain section fix, multi-line text fix, 5%
viewBox margin) come from
<https://github.com/terriblefire/eagle2svg> — see that repo's
`README_MODIFICATIONS.md` for the change list and rationale.

The vendored sources retain their original BSD licensing; only their
internal `from eagle2svg import …` statements were rewritten to relative
imports so the package can live inside `tflab`. The rest of `tflab` is
GPL-2.0-or-later, but BSD allows being combined with GPL'd code, and the
vendored module is consumed only internally by `tflab.eagle_pdf`.
