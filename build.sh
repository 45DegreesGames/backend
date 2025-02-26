#!/bin/bash
set -e

echo "Iniciando script de construcción"

# Instalar dependencias de Python
echo "Instalando dependencias de Python..."
pip install -r requirements.txt

# Instalar TeX Live básico (para pdflatex)
echo "Instalando TeX Live para soporte de LaTeX..."
apt-get update
apt-get install -y texlive-latex-base texlive-fonts-recommended

echo "Comprobando instalación de pdflatex..."
pdflatex --version || echo "Advertencia: pdflatex no está disponible"

echo "Instalación completada con éxito" 