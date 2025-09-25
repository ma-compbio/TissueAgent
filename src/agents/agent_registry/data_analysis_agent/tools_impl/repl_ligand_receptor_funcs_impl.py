FindLigandReceptorInteractionsDescription = '''
Computes ligand–receptor interaction scores between sender and receiver clusters.
Requires that spatial clustering (e.g. Leiden) has already been performed.

Args:
  adata (AnnData): the AnnData object to find ligand receptor interactions of
  cluster_key (str): key of spatial cluster labels in adata.obs (e.g. "leiden", "cluster", etc.)
  database (str): which LR database to use (default: CellPhoneDB)

Returns:
  str: status message

Updates to adata:
  Writes a dictionary containing keys ['means', 'pvalues', 'metadata'] into `adata.uns["{cluster_key}_ligrec"]`.
'''.strip()

FindLigandReceptorInteractionsCode = r'''
def find_ligand_receptor_interactions(
    adata: AnnData,
    cluster_key: str,
    database: str="CellPhoneDB",
) -> str:

    if cluster_key not in adata.obs:
        return "Error: Parameter cluster_key=\"{cluster_key}\" not found. Perform a spatial clustering first!"
    
    try:
        sq.gr.ligrec(
            adata,
            cluster_key=cluster_key,
            database=database,
            n_perms=5,
            threshold=0,
            use_raw=False,
            numba_parallel=False,
        )

        key_added = f"{cluster_key}_ligrec"
        return "Success: ligand-receptor interactions stored under adata.uns[\"{key_added}\"]"

    except Exception as e:
        return f"Error: {str(e)}"
'''.strip()

PlotLigandReceptorInteractionsDescription = '''
Plots ligand–receptor interaction scores between specified source and target clusters and saves the result as an image file.
Requires that ligand–receptor analysis has already been computed and stored in `adata.uns["{cluster_key}_ligrec"]`.

Args:
  adata (AnnData): the AnnData object containing precomputed ligand–receptor results
  cluster_key (str): key of cluster labels in `adata.obs` (e.g. “leiden”, “cluster”, etc.)
  filename (Path or str, optional): where to save the interaction plot; must reside within `DATA_DIR` (default: `DATA_DIR/"lr_interactions.png"`)
  source_groups (Sequence[str], optional): cluster IDs to use as sender groups (default: all)
  target_groups (Sequence[str], optional): cluster IDs to use as receiver groups (default: all)

Returns:
  str: status message
'''.strip()

PlotLigandReceptorInteractionsCode = r'''
def plot_ligand_receptor_interactions(
    adata: AnnData,
    cluster_key: str,
    filename: Optional[Union[Path, str]]=None,
    source_groups: Optional[Sequence[str]]=None,
    target_groups: Optional[Sequence[str]]=None,
) -> str:
    if filename is None:
        filename = DATA_DIR / "lr_interactions.png"
    filename = Path(filename)
    if DATA_DIR not in filename.parents and filename != DATA_DIR:
        return f"Error: filename \"{filename}\" must be a subdirectory of DATA_DIR."
    
    try: 
        sq.pl.ligrec(
            adata,
            cluster_key="leiden",
            source_groups="7",
            target_groups=["1"],
            pvalue_threshold=0.05,
            title="Ligand–Receptor Interactions",
            save=filename,
        )

        return f"Success: ligand-receptor interaction plot saved as \"{filename}\""
        
    except Exception as e:
        return f"Error: {str(e)}"
'''.strip()

PlotLigandReceptorHeatmapDescription = '''
Computes and saves a heatmap of averaged top-n ligand–receptor interaction scores between sender and receiver clusters.
Requires that ligand–receptor analysis has already been computed and stored in adata.uns["{cluster_key}_ligrec"].

Args:
  adata (AnnData): the AnnData object containing precomputed ligand–receptor results
  cluster_key (str): key of cluster labels in `adata.obs` (e.g. “leiden”, “cluster”, etc.)
  filename (Path or str, optional): where to save the heatmap; must reside within `DATA_DIR` (default: `DATA_DIR/"lr_heatmap.png"`)
  top_n (int, optional): number of highest-scoring interactions per sender–receiver pair to average (default: 5)

Returns:
  str: status message
'''.strip()

PlotLigandReceptorHeatmapCode = r'''
def plot_ligand_receptor_heatmap(
    adata: AnnData,
    cluster_key: str,
    filename: Optional[Union[Path, str]]=None,
    top_n: int=5
) -> str:
    if filename is None:
        filename = DATA_DIR / "lr_heatmap.png"
    filename = Path(filename)
    if DATA_DIR not in filename.parents and filename != DATA_DIR:
        return f"Error: filename \"{filename}\" must be a subdirectory of DATA_DIR."
    
    ligrec = adata.uns.get(f"{cluster_key}_ligrec")
    if ligrec is None:
        return f"Error: key \"{cluster_key}_ligrec\" not found in `adata.uns`. Find ligand-receptor interactions first!"
    means_df = ligrec.get("means")

    try: 
        if means_df is None or not isinstance(means_df, pd.DataFrame):
            raise ValueError
        senders   = list(means_df.columns.levels[0])
        receivers = list(means_df.columns.levels[1])
    except:
        return f"Error: entry \"{cluster_key}_ligrec\" is incorrectly formatted"

    try:
        agg = pd.DataFrame(index=senders, columns=receivers, dtype=float)
        for s in senders:
            for r in receivers:
                col = means_df[(s, r)]
                if col.isnull().all():
                    agg.at[s, r] = 0.0
                else:
                    top_vals = col.sort_values(ascending=False).head(top_n)
                    agg.at[s, r] = top_vals.mean()
        
        plt.figure(figsize=(max(8, len(receivers)*0.5), max(6, len(senders)*0.5)))
        sns.heatmap(
            agg,
            cmap="viridis",
            cbar_kws={"label": f"mean of top {top_n} scores"},
            xticklabels=True,
            yticklabels=True
        )
        plt.title("Ligand–Receptor Interaction Scores")
        plt.xlabel("Receiver Cluster")
        plt.ylabel("Sender Cluster")
        plt.tight_layout()
        plt.savefig(filename, dpi=150)
        plt.close()
        
        return f"Success: heatmap generated and saved as \"{filename}\"."
    
    except Exception as e:
        return f"Error: {e}"
'''.strip()

QueryInteractionAtCoordinatesDescription = '''
Returns the ligand–receptor interaction score for a specific pair between the sender spot closest to (x,y) and its neighboring receiver spots.
Requires spatial neighbors graph to be computed.

Args:
  adata (AnnData): the AnnData object containing spatial neighbor graph in `adata.obsp`
  ligand (str): ligand name to query (must be in `adata.var_names`)
  receptor (str): receptor name to query (must be in `adata.var_names`)
  x (float): x-position of spatial position
  y (float): y-position of spatial position

Returns:
  str: status message on error
  dict: { "LIGAND-RECEPTOR": best_score }
'''.strip()

QueryInteractionAtCoordinatesCode = r'''
def query_interaction_at_coordinates(
    adata: AnnData,
    ligand: str,
    receptor: str,
    x: float,
    y: float
) -> Union[str, Dict[str, float]]:

    missing = [g for g in (ligand, receptor) if g not in adata.var_names]
    if missing:
        return f"Error: gene(s) not found in `adata.var_names`: {', '.join(missing)}"

    if "spatial" not in adata.obsm:
        return "Error: spatial coordinates not found in `adata.obsm[\"spatial\"]`"
    coords = adata.obsm["spatial"]
    
    try:
        target = np.array([x, y])
        dists = np.linalg.norm(coords - target, axis=1)
        sender_idx = int(np.argmin(dists))

        for key in ("spatial_connectivities", "spatial_connectives", "spatial_neighbors"):
            if key in adata.obsp:
                nbr_mat = adata.obsp[key]
                break
        else:
            return "Error: No spatial neighbor graph found in adata.obsp. Run pp.spatial_neighbors or similar!"

        if hasattr(nbr_mat, "getrow"):
            neigh_idx = nbr_mat.getrow(sender_idx).indices
        else:
            neigh_idx = np.where(nbr_mat[sender_idx] != 0)[0]

        li_idx = adata.var_names.get_loc(ligand)
        re_idx = adata.var_names.get_loc(receptor)
        expr_l = float(adata.X[sender_idx, li_idx])

        scores = []
        for j in neigh_idx:
            expr_r = float(adata.X[j, re_idx])
            scores.append(expr_l * expr_r)

        best = max(scores) if scores else 0.0
        return {f"{ligand}-{receptor}": best}

    except Exception as e:
        return f"Error: {e}"
'''.strip()


PlotInteractionNetworkDescription = '''
Constructs and plots a network graph of clusters connected by top ligand–receptor pairs.
Requires that ligand–receptor analysis has already been computed and stored in adata.uns["{cluster_key}_ligrec"].

Args:
  adata (AnnData): the AnnData object containing precomputed ligand–receptor results
  cluster_key (str): key of cluster labels in `adata.obs` (e.g. “leiden”, “cluster”, etc.)
  filename (Path or str, optional): where to save the heatmap; must reside within `DATA_DIR` (default: `DATA_DIR/"lr_interactions.png"`)
  score_thresh (float, optional): minimum interaction score to include an edge (default: 1.0)
  clusters: (Sequence[str], optiona]): if provided, a subset of cluster names to restrict graph to (default: all clusters)

Returns:
  str: status message
'''.strip()

PlotInteractionNetworkCode = r'''
def plot_interaction_network(
    adata: AnnData,
    cluster_key: str,
    filename: Optional[Union[Path, str]]=None,
    score_thresh: float=0.1,
    clusters: Optional[Sequence[str]]=None
) -> str:

    if filename is None:
        filename = DATA_DIR / "lr_network.png"
    filename = Path(filename)
    if DATA_DIR not in filename.parents and filename != DATA_DIR:
        return f"Error: filename \"{filename}\" must be a subdirectory of DATA_DIR"

    ligrec = adata.uns.get(f"{cluster_key}_ligrec")
    if ligrec is None:
        return f"Error: key \"{cluster_key}_ligrec\" not found in `adata.uns`. Compute ligand–receptor interactions first!"
    means_df = ligrec.get("means")
    if means_df is None or not isinstance(means_df, pd.DataFrame):
        return f"Error: entry \"{cluster_key}_ligrec\" is incorrectly formatted (missing \"means\" DataFrame)."

    try:
        means = means_df.copy()
        if clusters is not None:
            all_senders = means.columns.get_level_values(0).unique()
            all_receivers = means.columns.get_level_values(1).unique()
            missing = [c for c in clusters if c not in all_senders or c not in all_receivers]
            if missing:
                return f"Error: cluster(s) not found: {', '.join(missing)}"
            mask = (
                means.columns.get_level_values(0).isin(clusters) &
                means.columns.get_level_values(1).isin(clusters)
            )
            means = means.loc[:, mask]
            if means.shape[1] == 0:
                return "Error: no sender–receiver pairs remain after clustering subsetting"

        stacked = means.stack([0, 1]).rename("score").dropna().astype(float).reset_index()
        stacked.columns = ["ligand", "receptor", "sender", "receiver", "score"]
        filtered = stacked[stacked["score"] >= score_thresh]
        if filtered.empty:
            return f"Error: no interactions with score ≥ {score_thresh} after filtering"

        top_idx = filtered.groupby(["sender", "receiver"])["score"].idxmax()
        top_df = filtered.loc[top_idx]

        G = nx.DiGraph()
        for _, row in top_df.iterrows():
            G.add_edge(
                row["sender"],
                row["receiver"],
                ligand=row["ligand"],
                receptor=row["receptor"],
                weight=row["score"]
            )

        pos = nx.spring_layout(G, seed=0)
        plt.figure(figsize=(8, 6))
        nx.draw_networkx_nodes(G, pos, node_size=700)
        nx.draw_networkx_labels(G, pos, font_size=10)
        widths = [d["weight"] for _, _, d in G.edges(data=True)]
        nx.draw_networkx_edges(G, pos, arrowstyle="->", arrowsize=6, width=widths)
        edge_labels = {
            (u, v): f"{d['ligand']}-{d['receptor']}"
            for u, v, d in G.edges(data=True)
        }
        nx.draw_networkx_edge_labels(G, pos, edge_labels=edge_labels, font_size=8)

        plt.title(f"L–R Network (score ≥ {score_thresh})")
        plt.tight_layout()
        plt.savefig(filename, dpi=150)
        plt.close()

        return f"Success: network graph generated and saved as \"{filename}\""

    except Exception as e:
        return f"Error: {e}"
'''.strip()
