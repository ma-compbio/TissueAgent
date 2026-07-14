{
  description = "TissueAgent development environment";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        pythonRuntimeLibs = with pkgs; [ stdenv.cc.cc.lib zlib ];
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            nodejs_22
            nodePackages.npm
            python312
            uv
            docker-client
          ] ++ pythonRuntimeLibs;

          LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath pythonRuntimeLibs;

          shellHook = ''
            echo "TissueAgent dev shell - node $(node --version), npm $(npm --version)"
          '';
        };
      }
    );
}
