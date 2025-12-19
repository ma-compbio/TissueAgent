import marimo

__generated_with = "0.17.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import pandas as pd
    from pathlib import Path

    def aggregate_lr_means(df):
        agg = df.groupby(["ligand_complex", "receptor_complex"])["lr_means"].mean()
        agg.index = [f"{ligand}__{receptor}" for ligand, receptor in agg.index]
        return agg

    def build_feature_matrix(file_map):
        feature_series_list = []
        labels = []
        for label, path in file_map.items():
            df = pd.read_csv(path)
            s = aggregate_lr_means(df)
            feature_series_list.append(s)
            labels.append(label)
        X = pd.concat(feature_series_list, axis=1).T
        X = X.fillna(0.0)
        y = pd.Series(labels, name="phenotype")
        return X, y

    file_map = {
        "AD": Path("lr_results_AD.csv"),
        "control": Path("lr_results_control.csv"),
        "early_AD": Path("lr_results_earlyAD.csv"),
    }

    X, y = build_feature_matrix(file_map)
    X.head(), y

    return X, y


@app.cell
def _(y):
    from sklearn.preprocessing import LabelEncoder

    def encode_labels(y):
        le = LabelEncoder()
        y_encoded = le.fit_transform(y)
        return y_encoded, le

    y_encoded, label_encoder = encode_labels(y)
    y_encoded, list(label_encoder.classes_)
    return (y_encoded,)


@app.cell
def _(X, y_encoded):
    from sklearn.model_selection import cross_val_score
    from sklearn.preprocessing import StandardScaler
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    def build_baseline_pipeline():
        pipe = Pipeline([
            ("scaler", StandardScaler(with_mean=False)),
            ("clf", LogisticRegression(max_iter=1000, multi_class="multinomial"))
        ])
        return pipe

    pipeline = build_baseline_pipeline()
    scores = cross_val_score(pipeline, X, y_encoded, cv=min(3, len(y_encoded)))
    scores.mean(), scores.std()
    return


@app.cell
def _():
    return


if __name__ == "__main__":
    app.run()
