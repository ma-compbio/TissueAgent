# squidpy.datasets.visium

### squidpy.datasets.visium(sample_id, \*, include_hires_tiff=False, base_dir=None)

Download Visium [datasets](https://support.10xgenomics.com/spatial-gene-expression/datasets) from *10x Genomics*.

* **Parameters:**
  * **sample_id** ([`Literal`](https://docs.python.org/3/library/typing.html#typing.Literal)[`'V1_Breast_Cancer_Block_A_Section_1'`, `'V1_Breast_Cancer_Block_A_Section_2'`, `'V1_Human_Heart'`, `'V1_Human_Lymph_Node'`, `'V1_Mouse_Kidney'`, `'V1_Adult_Mouse_Brain'`, `'V1_Mouse_Brain_Sagittal_Posterior'`, `'V1_Mouse_Brain_Sagittal_Posterior_Section_2'`, `'V1_Mouse_Brain_Sagittal_Anterior'`, `'V1_Mouse_Brain_Sagittal_Anterior_Section_2'`, `'V1_Human_Brain_Section_1'`, `'V1_Human_Brain_Section_2'`, `'V1_Adult_Mouse_Brain_Coronal_Section_1'`, `'V1_Adult_Mouse_Brain_Coronal_Section_2'`, `'Targeted_Visium_Human_Cerebellum_Neuroscience'`, `'Parent_Visium_Human_Cerebellum'`, `'Targeted_Visium_Human_SpinalCord_Neuroscience'`, `'Parent_Visium_Human_SpinalCord'`, `'Targeted_Visium_Human_Glioblastoma_Pan_Cancer'`, `'Parent_Visium_Human_Glioblastoma'`, `'Targeted_Visium_Human_BreastCancer_Immunology'`, `'Parent_Visium_Human_BreastCancer'`, `'Targeted_Visium_Human_OvarianCancer_Pan_Cancer'`, `'Targeted_Visium_Human_OvarianCancer_Immunology'`, `'Parent_Visium_Human_OvarianCancer'`, `'Targeted_Visium_Human_ColorectalCancer_GeneSignature'`, `'Parent_Visium_Human_ColorectalCancer'`, `'Visium_FFPE_Mouse_Brain'`, `'Visium_FFPE_Mouse_Brain_IF'`, `'Visium_FFPE_Mouse_Kidney'`, `'Visium_FFPE_Human_Breast_Cancer'`, `'Visium_FFPE_Human_Prostate_Acinar_Cell_Carcinoma'`, `'Visium_FFPE_Human_Prostate_Cancer'`, `'Visium_FFPE_Human_Prostate_IF'`, `'Visium_FFPE_Human_Normal_Prostate'`]) – Name of the Visium dataset.
  * **include_hires_tiff** ([`bool`](https://docs.python.org/3/library/functions.html#bool)) – Whether to download the high-resolution tissue section into
    [`anndata.AnnData.uns`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.uns.html#anndata.AnnData.uns) `['spatial']['{sample_id}']['metadata']['source_image_path']`.
  * **base_dir** ([`PathLike`](https://docs.python.org/3/library/os.html#os.PathLike)[[`str`](https://docs.python.org/3/library/stdtypes.html#str)] | [`str`](https://docs.python.org/3/library/stdtypes.html#str) | [`None`](https://docs.python.org/3/library/constants.html#None)) – Directory where to download the data. If None, use [`scanpy._settings.ScanpyConfig.datasetdir`](https://scanpy.readthedocs.io/en/stable/generated/scanpy._settings.ScanpyConfig.datasetdir.html#scanpy._settings.ScanpyConfig.datasetdir).
* **Return type:**
  [`AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData)
* **Returns:**
  :
  Spatial [`anndata.AnnData`](https://anndata.readthedocs.io/en/stable/generated/anndata.AnnData.html#anndata.AnnData).
