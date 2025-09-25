# SpatialAgent

SpatialAgent is a multi-agent system for automating spatial transcriptomics data analysis and accelerating scientific discovery.

## Installation

1. **Clone the repository**  
   ```bash
   git clone https://github.com/wenduocheng/SpatialAgent.git
   cd SpatialAgent


2. **Using [conda](https://anaconda.org/anaconda/conda)**:

   > *If this is your first time using Conda, initialize your shell (once):*
   >
   > ```bash
   > conda init bash     # or zsh, fish, etc.
   > source ~/.bashrc    # or ~/.zshrc
   > ```

   Create and activate a Conda environment, then install dependencies:

   ```bash
   conda env create -f devenv/environment.yml
   ```

3. **Using [venv](https://docs.python.org/3/library/venv.html)** (requires Python 3.9):

   ```bash
   python3.9 -m venv .venv
   # macOS/Linux
   source .venv/bin/activate
   # Windows (PowerShell)
   .venv\Scripts\Activate.ps1
   
   pip install --upgrade pip
   pip install -r devenv/requirements.txt
   ```

4. **Configure API keys** (optional)
    Append your keys to your shell config (`~/.bashrc`, `~/.zshrc`, etc.):

   ```bash
   echo 'export OPENAI_API_KEY="YOUR_OPENAI_API_KEY"'   >> ~/.bashrc
   echo 'export ANTHROPIC_API_KEY="YOUR_ANTHROPIC_API_KEY"' >> ~/.bashrc
   echo 'export SERP_API_KEY="YOUR_SERP_API_KEY"'       >> ~/.bashrc
   source ~/.bashrc
   ```

5. **Build Documentation** (to do)

## Usage

Launch the Streamlit app with the following command and follow the instructions displayed.
```bash
PYTHONPATH=$(pwd)/src python -m streamlit run src/app.py
```

