{
  description = "TissueAgent development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        pythonRuntimeLibs = with pkgs; [ stdenv.cc.cc.lib zlib ];
        rEnv = pkgs.rWrapper.override {
          packages = with pkgs.rPackages; [
            Seurat
            SeuratObject
            hdf5r
            Matrix
            remotes
          ];
        };
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            nodejs_22
            nodePackages.npm
            python312
            uv
            docker-client
            rEnv
          ] ++ pythonRuntimeLibs;

          LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath pythonRuntimeLibs;

          shellHook = ''
            echo "TissueAgent dev shell - node $(node --version), npm $(npm --version)"
          '';
        };
      }
    );
}
