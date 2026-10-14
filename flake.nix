{
  description = "Development shell";

  inputs.nix-devenv.url = "github:dryvist/nix-devenv?ref=v0";
  # The locked nixpkgs of the dev shell, named so CI can run `nix shell --inputs-from . nixpkgs#<pkg>`.
  inputs.nixpkgs.follows = "nix-devenv/channels/nixpkgs";

  outputs =
    { nix-devenv, ... }:
    {
      devShells = builtins.mapAttrs (_: shells: {
        default = shells.ansible-apps;
      }) nix-devenv.devShells;
    };
}
