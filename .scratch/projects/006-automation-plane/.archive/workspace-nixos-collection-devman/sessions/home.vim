" mini.sessions-compatible homepage for multi-repo NixOS workspaces

set sessionoptions=blank,buffers,curdir,folds,help,tabpages,winsize,winpos,terminal

if isdirectory('repos/nixos-config')
  tabnew
  execute 'lcd repos/nixos-config'
  edit flake.nix
endif

if isdirectory('repos/home-config')
  tabnew
  execute 'lcd repos/home-config'
  edit home.nix
endif

if isdirectory('repos/nixpkgs')
  tabnew
  execute 'lcd repos/nixpkgs'
  edit README.md
endif

if isdirectory('repos/secrets')
  tabnew
  execute 'lcd repos/secrets'
  edit README.md
endif

if filereadable('.devman/interaction.md')
  tabnew
  execute 'lcd .'
  edit .devman/interaction.md
endif
