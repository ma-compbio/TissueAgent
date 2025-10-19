## scanpy.cli.main(argv=None, \*, check=True, \*\*runargs)
Run a builtin scanpy command or a scanpy-\* subcommand.

Uses `subcommand.run()` for the latter:
`~run(['scanpy', *argv], **runargs)`

* **Return type:**
  [`CompletedProcess`](https://docs.python.org/3/library/subprocess.html#subprocess.CompletedProcess) | [`None`](https://docs.python.org/3/library/constants.html#None)

