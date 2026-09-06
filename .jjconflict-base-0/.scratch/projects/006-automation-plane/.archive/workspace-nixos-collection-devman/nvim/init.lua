vim.opt.number = true
vim.opt.relativenumber = true
vim.opt.signcolumn = "yes"
vim.opt.updatetime = 300

vim.keymap.set("n", "<leader>sh", ":source .devman/sessions/home.vim<CR>", {
  desc = "Load NixOS workspace home session",
})
