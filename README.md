# Header Plugin (v0.5 alpha)
Author: **River Loop Security LLC**

_Pre-process headers and load them into BinaryNinja, setting types and function prototypes from them._

## Description:

This processes a header file and attempts to coalesce it into a format which BinaryNinja will accept.

It can be run as a GUI BinaryNinja plugin, or as a command line tool.

> NOTE: This does _NOT_ work on C++ headers as BinaryNinja only supports C typing.

Contributions and improvements are very welcome.

## Minimum Version

This plugin requires the following minimum version of Binary Ninja:

 * release - TODO
 * dev - TODO

## Required Dependencies

The following dependencies are required for this plugin:

 * pip - pcpp

## License

This plugin is released under a [MIT](LICENSE) license.

## CLI Usage

If parameters are not provided and are required, they will be prompted for as interactive prompts.

Example CLI usage:
```bash
$ python __init__.py -d target/include -i main.h -w binary.bndb -b target/bin/binary
```

Note that for development purposes, the `-r` and `--direct` flags may be helpful.
