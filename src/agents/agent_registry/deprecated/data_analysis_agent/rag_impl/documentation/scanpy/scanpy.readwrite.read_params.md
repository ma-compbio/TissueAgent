## scanpy.readwrite.read_params(filename, \*, as_header=False)
Read parameter dictionary from text file.

Assumes that parameters are specified in the format:

```default
par1 = value1
par2 = value2
```

Comments that start with ‘#’ are allowed.

* **Parameters:**
  **filename** 
  : Filename of data file.

  **asheader**
  : Read the dictionary from the header (comment section) of a file.
* **Return type:**
  [`dict`](https://docs.python.org/3/library/stdtypes.html#dict)[[`str`](https://docs.python.org/3/library/stdtypes.html#str), [`int`](https://docs.python.org/3/library/functions.html#int) | [`float`](https://docs.python.org/3/library/functions.html#float) | [`bool`](https://docs.python.org/3/library/functions.html#bool) | [`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)]
* **Returns:**
  Dictionary that stores parameters.

