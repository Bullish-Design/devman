vim.o.number = true
vim.o.relativenumber = true

vim.api.nvim_create_user_command("WorkspaceHome", function()
  vim.cmd("source .devman/sessions/home.vim")
end, {})
