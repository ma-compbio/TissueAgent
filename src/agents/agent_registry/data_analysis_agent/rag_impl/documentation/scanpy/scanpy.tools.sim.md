## scanpy.tools.sim(model, \*, params_file=True, tmax=None, branching=None, nrRealizations=None, noiseObs=None, noiseDyn=None, step=None, seed=None, writedir=None)
Simulate dynamic gene expression data [[Wittmann *et al.*, 2009](../references.md#id60)] [[Wolf *et al.*, 2018](../references.md#id61)].

Sample from a stochastic differential equation model built from
literature-curated boolean gene regulatory networks, as suggested by
Wittmann *et al.* [[2009](../references.md#id60)]. The Scanpy implementation can be found in Wolf *et al.* [[2018](../references.md#id61)].

* **Parameters:**
  **model** 
  : Model file in ‘sim_models’ directory.

  **params_file** 
  : Read default params from file.

  **tmax** 
  : Number of time steps per realization of time series.

  **branching** 
  : Only write realizations that contain new branches.

  **nrRealizations** 
  : Number of realizations.

  **noiseObs** 
  : Observatory/Measurement noise.

  **noiseDyn** 
  : Dynamic noise.

  **step** 
  : Interval for saving state of system.

  **seed** 
  : Seed for generation of random numbers.

  **writedir** 
  : Path to directory for writing output files.
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)
* **Returns:**
  Annotated data matrix.

### Examples

See this [use case](https://github.com/scverse/scanpy_usage/tree/master/170430_krumsiek11)

