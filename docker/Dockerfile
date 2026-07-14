FROM r-base:latest

# System dependencies for Python, R kernel, and scientific packages.
# The geospatial libs (gdal/geos/proj/udunits) are required by CARD's R
# dependencies (sf, concaveman, spatstat); libcurl/ssl/xml for remotes install.
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip \
    python3-venv \
    python3-dev \
    libzmq3-dev \
    libhdf5-dev \
    libfribidi-dev \
    libharfbuzz-dev \
    pkg-config \
    gcc \
    g++ \
    gfortran \
    libcurl4-openssl-dev \
    libssl-dev \
    libxml2-dev \
    libgdal-dev \
    libgeos-dev \
    libproj-dev \
    libudunits2-dev \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------
# Python environment
# -----------------------------------------
RUN python3 -m venv /opt/venv \
    && chmod -R 777 /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Jupyter Kernel Gateway + IPython kernel
RUN pip install --no-cache-dir \
    jupyter_kernel_gateway \
    ipykernel

# Pre-install spatial transcriptomics packages
RUN pip install --no-cache-dir \
    scanpy \
    squidpy \
    anndata \
    liana \
    decoupler \
    matplotlib \
    seaborn \
    scipy \
    pandas \
    numpy \
    plotnine \
    tangram-sc

# Cell-cell communication ensemble (LIANA+ / COMMOT / stLearn) + plotting helpers.
# Note: stlearn pulls torch + full CUDA runtime (~3-5 GB).
RUN pip install --no-cache-dir \
    commot \
    stlearn \
    pycirclize \
    upsetplot

# commot 0.0.3 references np.Inf, which NumPy 2.0 removed. Patch inline.
RUN sed -i 's/np\.Inf\b/np.inf/g' \
    /opt/venv/lib/python*/site-packages/commot/_optimal_transport/_usot.py

# Re-open venv perms so uid 1000 can install additional packages at runtime.
# The earlier chmod ran before the pip installs above, so files/dirs created
# by root (e.g. /opt/venv/share/*) were left 755 root:root.
RUN chmod -R a+w /opt/venv

# -----------------------------------------
# R environment
# -----------------------------------------
RUN mkdir -p /opt/R/library && chmod -R 777 /opt/R/library
ENV R_LIBS_USER="/opt/R/library"

# Install IRkernel for Jupyter
RUN Rscript -e "install.packages('IRkernel', repos='https://cloud.r-project.org'); IRkernel::installspec(user = FALSE)"

# Pre-install CARD (deconvolution). BiocManager pulls its two Bioconductor
# deps (SingleCellExperiment, SummarizedExperiment); remotes::install_github
# pulls the CRAN Imports automatically. See knowledge/skills/deconvolution_card.md.
RUN Rscript -e "install.packages(c('remotes','BiocManager'), repos='https://cloud.r-project.org'); \
    BiocManager::install(c('SingleCellExperiment','SummarizedExperiment'), update=FALSE, ask=FALSE); \
    remotes::install_github('YMa-lab/CARD', upgrade='never')"

# -----------------------------------------
# Non-root user
# -----------------------------------------
# r-base already has a user (docker) at UID 1000; reuse it so bind-mount
# permissions match the host user (also typically UID 1000).
RUN usermod -l agent -d /home/agent -m docker 2>/dev/null \
    || useradd -m -u 1000 agent; \
    mkdir -p /workspace && chown 1000:1000 /workspace
USER 1000
WORKDIR /workspace

EXPOSE 8888
CMD ["jupyter", "kernelgateway", \
     "--KernelGatewayApp.ip=0.0.0.0", \
     "--KernelGatewayApp.port=8888", \
     "--KernelGatewayApp.api=kernel_gateway.jupyter_websocket"]
