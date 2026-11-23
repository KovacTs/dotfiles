# Ruta de instalación de Oh My Zsh
export ZSH="$HOME/.oh-my-zsh"

# Cargar zsh-autocomplete antes de Oh My Zsh (y antes de compinit)
source "$ZSH/custom/plugins/zsh-autocomplete/zsh-autocomplete.plugin.zsh"

# Tema de Oh My Zsh (puedes ver más en ~/.oh-my-zsh/themes/)
ZSH_THEME="robbyrussell"

# Plugins (zsh-syntax-highlighting siempre debe ir al final)
plugins=(
    git
    zsh-autosuggestions
    zsh-syntax-highlighting
)

source "$ZSH/oh-my-zsh.sh"

# Restaurar atajos de flechas de zsh-autocomplete (sobrescritos por Oh My Zsh)
bindkey '^[[A' up-line-or-search
bindkey '^[OA' up-line-or-search
bindkey '^[[B' down-line-or-select
bindkey '^[OB' down-line-or-select

# Historial ampliado
HISTSIZE=10000
SAVEHIST=10000
setopt HIST_IGNORE_DUPS
setopt HIST_IGNORE_SPACE

# Alias útiles
alias ls='ls --color=auto'
alias grep='grep --color=auto'
