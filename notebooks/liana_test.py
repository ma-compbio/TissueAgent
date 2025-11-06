import marimo

__generated_with = "0.17.2"
app = marimo.App(width="medium")


@app.cell
def _():
    from langchain_experimental.utilities import PythonREPL

    repl = PythonREPL()
    return (repl,)


@app.cell
def _(repl):
    print(repl.run("""
    import scanpy as sc

    from pathlib import Path

    dataset_path = Path("/Users/dustinm/Projects/research/ma-lab/SpatialAgent/test/datasets/lohoff_et_al_seqfish.h5ad")

    adata = sc.read_h5ad(dataset_path)
    adata.obs.head()

    species = "mouse"

    print(adata)
    """))
    return


@app.cell
def _(repl):
    print(repl.run("""
    import pandas as pd
    import numpy as np
    from collections import Counter
    def build_gene_map(var_names, species: str) -> pd.DataFrame:
        import pandas as pd
        import numpy as np

        original = pd.Series(var_names, name="original_id").astype(str)
        mapped = original.copy()
        status = pd.Series(["kept"] * len(original), name="status")
        is_ensembl = mapped.str.startswith(("ENSG", "ENSMUSG", "ENST", "ENSMUST"))
        status[is_ensembl] = "unmapped_ensembl"
        mapped[is_ensembl] = mapped[is_ensembl].str.replace(r"\.\d+$", "", regex=True)
        mapped = mapped.str.strip()
        mapped[mapped == ""] = np.nan
        status[mapped.isna()] = "unmapped_empty"
        dup_mask = mapped.duplicated(keep="first")
        status[(~mapped.isna()) & dup_mask] = "duplicate_mapped_symbol"
        df = pd.DataFrame({"original_id": original, "mapped_symbol": mapped, "species": species, "status": status})
        return df
    gene_map_df = build_gene_map(list(adata.var_names), species)
    print("Gene map preview:")
    print(gene_map_df.head(10).to_string(index=False))
    print("Gene map status counts:")
    print(gene_map_df["status"].value_counts().to_string())
    print("Unique mapped symbols (non-null):", gene_map_df["mapped_symbol"].notna().sum(), "of", gene_map_df.shape[0])
    """))
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
