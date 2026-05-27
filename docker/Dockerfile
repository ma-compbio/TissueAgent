FROM r-base:latest

# System dependencies for Python, R kernel, and scientific packages
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
    plotnine

# -----------------------------------------
# R environment
# -----------------------------------------
RUN mkdir -p /opt/R/library && chmod -R 777 /opt/R/library
ENV R_LIBS_USER="/opt/R/library"

# Install IRkernel for Jupyter
RUN Rscript -e "install.packages('IRkernel', repos='https://cloud.r-project.org'); IRkernel::installspec(user = FALSE)"

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
