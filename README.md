# Environment setup
```bash
# conda env
conda create --name pirel_env "python>=3.12"
conda activate pirel_env

# dependencies
pip install -r requirements.txt

# install NodeJS with NVM https://github.com/nvm-sh/nvm
wget -qO- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
nvm install 21.5.0
```

# Running PiREL

## On a subject from GFG benchmark
```bash
cd src
python p_learn_apply_rules.py --benchmark-name gfg --subject-names G0001 --is-three-split
```

## On a subject from SKEL benchmark
```bash
cd src
python p_learn_apply_rules.py --benchmark-name skel --subject-names colorsys
```

## Checking the results
Translated target program and learned translation rules can be checked in `logs/learn-rules` directory.