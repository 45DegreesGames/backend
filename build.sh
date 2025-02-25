#!/bin/bash

# Instalar dependencias de Python
pip install -r requirements.txt

# Instalar TeX Live básico (para pdflatex)
apt-get update
apt-get install -y texlive-latex-base texlive-fonts-recommended

echo "Instalación completada" 