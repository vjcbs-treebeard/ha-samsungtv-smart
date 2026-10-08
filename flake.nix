{
  description = "SamsungTV Smart development environment";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-25.05";

  outputs = { nixpkgs, ... }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
    in {
      devShells = nixpkgs.lib.genAttrs systems (system:
        let pkgs = import nixpkgs { inherit system; };
        in {
          default = pkgs.mkShell {
            packages = [
              pkgs.python313
              pkgs.uv
              pkgs.python313Packages.black
              pkgs.python313Packages.flake8
              pkgs.python313Packages.isort
            ];
            env.UV_PYTHON_DOWNLOADS = "never";
          };
        });
    };
}
