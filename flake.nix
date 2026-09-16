{
  description = "TissueAgent development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
    # scMultiSim entered nixpkgs after 24.11, so pin a newer nixpkgs just for
    # the R packages (and the libstdc++ used below), while keeping the
    # Python/Node toolchain on the original 24.11 pin.
    nixpkgs-r.url = "github:NixOS/nixpkgs/nixos-26.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, nixpkgs-r, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        pkgsR = nixpkgs-r.legacyPackages.${system};

        # R for the scMultiSim CCC benchmark (temp/scmultisim): provides
        # R + Rscript with scMultiSim (>= 1.2.0; 24.11 predates it), ape and
        # Matrix preinstalled -- no BiocManager::install() step needed.
        rEnv = pkgsR.rWrapper.override {
          packages = with pkgsR.rPackages; [ scMultiSim ape Matrix ];
        };

        # Use the NEWER libstdc++ (from nixpkgs-r) on LD_LIBRARY_PATH. It is
        # backward-compatible, so it satisfies both the 26.05 R binaries and the
        # 24.11 Python wheels. Sourcing it from 24.11 instead would shadow R's
        # newer libstdc++ and break R with a CXXABI version error.
        pythonRuntimeLibs = [ pkgsR.stdenv.cc.cc.lib pkgs.zlib ];
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            nodejs_22
            nodePackages.npm
            python312
            # _tkinter C-extension for the venv python (base python312 lacks it);
            # stlearn -> PIL.ImageTk -> tkinter needs it. The venv symlinks this
            # package's _tkinter*.so; keeping it here gc-roots that store path.
            python312Packages.tkinter
            uv
            docker-client
            rEnv
          ] ++ pythonRuntimeLibs;

          LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath pythonRuntimeLibs;

          shellHook = ''
            echo "TissueAgent dev shell - node $(node --version), npm $(npm --version), R $(R --version | head -n1)"
          '';
        };
      }
    );
}
