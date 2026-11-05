# Preferred Tools

The curated, vetted list of libraries the agent uses for common needs. When a task needs one
of these, the agent uses the listed package instead of researching alternatives. A package is
listed only after Heroku engineers have vetted it (license, maintenance, transitive
dependencies, install scripts, advisories, and that it builds on Heroku).

This file is the only one to edit. `references/preferred-tools.json` is generated from it:

    python3 scripts/build_tools_index.py            # regenerate the JSON
    python3 scripts/build_tools_index.py --check    # verify it is current (also run in CI)

Commit both files together. Every `##` heading below is a need and its text is the need id
(lowercase, hyphenated). A need has a `Description:` line, an `Aliases:` line (comma-separated
phrases that mean the same need) and a table with one row per stack. Stacks are `go`, `node`,
`python`, `rails` and `website`; the registry must match the stack (`go`, `npm`, `pypi`,
`rubygems`, `npm`). `Version` is the approved version and only a human changes it.

## qr-code

Description: Generate QR code images or data from text or URLs.
Aliases: qr, qr code, qr code generator, qrcode

| Stack | Package | Registry | Version | License | Link | Vetted on | Approved by |
|---|---|---|---|---|---|---|---|
