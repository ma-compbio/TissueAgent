# Prior Knowledge

LIANA+ (typically) relies heavily on prior knowledge to infer intercellular communication and the intracellular signaling pathways that are activated in response to communication. This notebook provides a brief overview of the prior knowledge typically used by LIANA+. 


```python
import liana as li
import omnipath as op
import decoupler as dc
```

## Ligand-Receptor Interactions

In the simplest case, for reproducibility purposes, LIANA+ provides a frozen set of interactions across resources. These are accessible through the `select_resource` function in the `resource` module. The resources that are currently supported are:


```python
li.resource.show_resources()
```

    
By default, `liana` uses the `consensus` resource, which is composed by multiple expert-curated ligand-receptor resources, including CellPhoneDB, CellChat, ICELLNET, connectomeDB2020, and CellTalkDB.



```python
resource = li.rs.select_resource('consensus')
resource.head()
```

All of the ligand-receptor resource in LIANA+ were pre-generated using the [OmniPath](https://github.com/saezlab/omnipath) meta-database. Though any custom resource can also be passed, including those provided by the user or generated using the `omnipath` client package. 

Via this client, in addition to ligand-receptor interactions, users can obtain the PubMed IDs of the references (`references`) that were used support each interaction, as well as the database that reported the interaction in the first place. 

Users can also modify the resource according to their preferences, for example:


```python
ligrec = op.interactions.import_intercell_network(
    interactions_params = {'license':'commercial'},
    transmitter_params = {'database':'CellChatDB'},
    receiver_params = {'database':'CellChatDB'},
    )
ligrec.head()

ligrec = ligrec.rename(columns={'genesymbol_intercell_source':'ligand', 'genesymbol_intercell_target':'receptor'})
ligrec = ligrec[['ligand', 'receptor', 'references'] + [col for col in ligrec.columns if col not in ['ligand', 'receptor', 'references']]]
ligrec.head()
```

This function provides a rich list of annotations, such as the modes of action,inhibition or stimulation, the curation effort, types of signalling, etc.
For a more comprehensive overview of the information that is available, please refer to the [OmniPath documentation](https://omnipathdb.org/).

## Homology Mapping

Similarly, LIANA+ provides on demand homology mapping beyond mouse symbols. It utilises the [HCOP database](https://www.genenames.org/help/hcop/) to obtain homologous genes across species. Specifically, we download the resource from the frequently-updated Bulk Download FTP section of the HCOP database: https://ftp.ebi.ac.uk/pub/databases/genenames/hcop/.

The homology mapping is accessible through the `resource` module:


```python
# let's say we are interested in zebrafish homologs of human genes
map_df = li.rs.get_hcop_orthologs(url='https://ftp.ebi.ac.uk/pub/databases/genenames/hcop/human_zebrafish_hcop_fifteen_column.txt.gz',
                                   columns=['human_symbol', 'zebrafish_symbol'],
                                   # NOTE: HCOP integrates multiple resource, so we can filter out mappings in at least 3 of them for confidence
                                   min_evidence=3
                                   )
# rename the columns to source and target, respectively for the original organism and the target organism
map_df = map_df.rename(columns={'human_symbol':'source', 'zebrafish_symbol':'target'})
map_df.tail()
```

Now that we've obtained the homologous genes, let's convert the resource to those genes:


```python
zfish = li.rs.translate_resource(resource,
                                 map_df=map_df,
                                 columns=['ligand', 'receptor'],
                                 replace=True,
                                 # NOTE that we need to define the threshold of redundancies for the mapping
                                 # in this case, we would keep mappings as long as they don't map to more than 2 zebrafish genes
                                 one_to_many=3
                                 )
```

### Obtain Mouse Homologs


```python
map_df = li.rs.get_hcop_orthologs(url='https://ftp.ebi.ac.uk/pub/databases/genenames/hcop/human_mouse_hcop_fifteen_column.txt.gz',
                                  columns=['human_symbol', 'mouse_symbol'],
                                   # NOTE: HCOP integrates multiple resource, so we can filter out mappings in at least 3 of them for confidence
                                   min_evidence=3
                                   )
# rename the columns to source and target, respectively for the original organism and the target organism
map_df = map_df.rename(columns={'human_symbol':'source', 'mouse_symbol':'target'})

# We will then translate
mouse = li.rs.translate_resource(resource,
                                 map_df=map_df,
                                 columns=['ligand', 'receptor'],
                                 replace=True,
                                 # Here, we will be harsher and only keep mappings that don't map to more than 1 mouse gene
                                 one_to_many=1
                                 )
mouse
```

If you use HCOP function, please reference the original HCOP papers:
- Eyre, T.A., Wright, M.W., Lush, M.J. and Bruford, E.A., 2007. HCOP: a searchable database of human orthology predictions. Briefings in bioinformatics, 8(1), pp.2-5.
- Yates, B., Gray, K.A., Jones, T.E. and Bruford, E.A., 2021. Updates to HCOP: the HGNC comparison of orthology predictions tool. Briefings in Bioinformatics, 22(6), p.bbab155.

<div class="alert alert-block alert-info">

All methods of LIANA+ accept a ``resource`` parameter that can be used to pass any custom resource, beyond such from homology conversion.

</div>

## Annotating Ligand-Receptors

In addition to ligand-receptors, we can also obtain other annotations via [OmniPath](https://github.com/saezlab/omnipath). While these can be tissue locations, TF regulons, cytokine signatures, or other types of annotations, the most common use case is to obtain the pathways that are associated with each ligand-receptor interaction.

### Pathway Annotations

We use commonly [PROGENy](https://www.nature.com/articles/s41467-017-02391-6) pathway weights to assign interactions to certain canonical pathways, such that all members of the interactions (i.e. incl. complex subunits) are present in the same pathway with the same weight sign. This is done to ensure that the interaction is not only present in the same pathway, but also that it is likely to be active in the same direction.


```python
# load PROGENy pathways, we use decoupler as a proxy as it formats the data in a more convenient way
progeny = dc.op.progeny(top=2500)
progeny.head()
```


```python
# load full list of ligand-receptor pairs
lr_pairs = li.resource.select_resource('consensus')
```

Then we use the `generate_lr_geneset` function from liana to assign the interactions to pathways. This function takes the ligand-receptor interactions and the pathway annotations, and returns a dataframe with annotated interactions.


```python
# generate ligand-receptor geneset
lr_progeny = li.rs.generate_lr_geneset(lr_pairs, progeny, lr_sep="^")
lr_progeny.head()
```

We can additionally performed enrichment analysis of certain ligand-receptor scores using this newly-generated dataframe. For example, see the [application with Tensor-cell2cell](https://liana-py.readthedocs.io/en/latest/notebooks/liana_c2c.html#Downstream-Analysis)

### Disease Annotations
As another example, we can also annotate ligand-receptors to diseases in which both the ligand and the receptor are involved.


```python
diseases = op.requests.Annotations.get(
    resources = ['DisGeNet']
    )
```


```python
diseases = diseases[['genesymbol', 'label', 'value']]
diseases = diseases.pivot_table(index='genesymbol',
                                columns='label', values='value',
                                aggfunc=lambda x: '; '.join(x)).reset_index()
diseases = diseases[['genesymbol', 'disease']]
diseases['disease'] = diseases['disease'].str.split('; ')
diseases = diseases.explode('disease')
lr_diseases = li.rs.generate_lr_geneset(lr_pairs, diseases, source='disease', target='genesymbol', weight=None, lr_sep="^")
lr_diseases.sort_values("interaction").head()
```

Let's check some protein of interest:


```python
lr_diseases[lr_diseases['interaction'].str.contains('SPP1')]
```

Following similar procedures, one may annotate ligand-receptors to any of the annotations available via OmniPath.

See `op.requests.Annotations.resources()`

## Intracellular Signaling

While we can obtain the pathways that are associated with each ligand-receptor interaction, we can also obtain the intracellular signaling pathways that are activated in response to the interaction. This is again done using the `omnipath` client package, but this time in combination with [decoupler](https://decoupler-py.readthedocs.io/en/latest/), which enables the enrichment of pathways, transcription factors, and other annotations.

One specific scenario, heavily reliant on OmniPath knowledge and enrichment analysis with decoupler is presented in the [Differential Analysis Vignette](https://liana-py.readthedocs.io/en/latest/notebooks/targeted.html).

There, to find putative causal networks between deregulated CCC interactions and transcription factors (TFs) we use:

### 1) a protein-protein interaction network


```python
ppis = op.interactions.OmniPath().get(genesymbols = True)
ppis.head()
```

### 2) Transcription Factor Regulons
Provided via the [CollecTRI](https://academic.oup.com/nar/article/51/20/10934/7318114?login=false) resource:


```python
dc.op.collectri(organism='human', remove_complexes=False, license='academic', verbose=False).head()
```

These are then linked using the a modification of the ILP problem proposed in [CARNIVAL](https://www.nature.com/articles/s41540-019-0118-z), solved using [CORNETO](https://github.com/saezlab/corneto) - a Unified Omics-Driven Framework for Network Inference.

## Metabolite-Receptor Interactions

Via LIANA+ we also provide access to the [MetalinksDB knowledge graph - a customisable database](https://github.com/biocypher/metalinks) of metabolite-receptor interactions, part of the [BioCypher](https://biocypher.org/) ecosystem. For more information please refer to [Farr et al, 2023](https://www.biorxiv.org/content/10.1101/2023.12.30.573715v1.abstract).

Specifically, to enable light-weight access, we have converted the MetalinksDB knowledge graph into a database.

This database is queried using `sqllite3` and we provide basic queries to customize according to the user's needs - e.g. disease, pathway, location.

We can check first the values within different tables of the database:


```python
li.resource.get_metalinks_values(table_name='disease', column_name='disease')[0:5]
```

Then we can obtain metabolite-receptor interactions, the metabolites of which have been reported to be associated with certain locations or diseases:


```python
li.resource.get_metalinks(source=['Stich', 'CellPhoneDB', 'NeuronChat'],
                          tissue_location='Brain',
                          biospecimen_location='Cerebrospinal Fluid (CSF)',
                          disease='Schizophrenia',
                          ).head()
```

This database contains both ligand-receptor (lr) and production-degradation (pd) metabolite-protein interactions - note `type`. It can further be filtered according to the user's needs, and can be queried as any other standard RDBMS.

For such cases, we also provide a utility function to print the database schema:


```python
li.rs.describe_metalinks()
```
