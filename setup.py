# @Author: Arthur Voronin <arthur>
# @Date:   11.05.2021
# @Filename: setup.py
# @Last modified by:   arthur
# @Last modified time: 21.06.2021

from setuptools import setup, find_packages
import sys

if sys.version_info.minor == 8:
    setup(name='pyrexMD',
          version='1.0',
          description='workflow orientated setup and analyses of contact-guided Replica Exchange Molecular Dynamics (requires GROMACS for MD)',
          license="MIT",
          author='Arthur Voronin',
          author_email='arthur.voronin@kit.edu',
          url='https://github.com/KIT-MBS/pyrexMD',
          packages=find_packages(),
          install_requires=[
              'autopep8>=1.5.7',
              'biopython==1.78',
              'duecredit>=0.9.1',
              'future>=0.18.2',
              'GromacsWrapper==0.8.0',
              'h5py>=2.10.0',
              'heat==1.0.0',
              'ipywidgets>=7.4.2',
              'jupyter>=1.0.0',
              'scikit-learn>=0.24.2',
              'nglview==2.0',
              'MDAnalysis>=1.1.1',
              'numpy>=1.18.2',
              'pdf2image>=1.10.0',
              'Pillow>=8.2.0',
              'pyperclip>=1.8.2',
              'pytest>=6.2.4',
              'pytest-cov>=2.12.1',
              'seaborn>=0.11.1',
              'termcolor>=1.1.0',
              'tqdm>=4.60.0',
              'widgetsnbextension>=3.5.1'
          ]
          )

if sys.version_info.minor == 6:
    setup(name='pyrexMD',
          version='1.0',
          description='workflow orientated setup and analyses of contact-guided Replica Exchange Molecular Dynamics (requires GROMACS for MD)',
          license="MIT",
          author='Arthur Voronin',
          author_email='arthur.voronin@kit.edu',
          url='https://github.com/KIT-MBS/pyrexMD',
          packages=find_packages(),
          install_requires=[
              'autopep8>=1.4.3',
              'biopython>=1.78',
              'duecredit>=0.9.1',
              'future>=0.18.2',
              'GromacsWrapper>=0.8.0',
              'h5py>=2.10.0',
              'heat==1.0.0',
              'ipywidgets>=7.4.2',
              'jupyter>=1.0.0',
              'MDAnalysis==1.1.1',
              'nglview==2.0',
              'numpy>=1.18.2',
              'pdf2image>=1.10.0',
              'Pillow>=8.2.0',
              'pyperclip>=1.8.2',
              'pytest>=6.2.4',
              'pytest-cov>=2.12.1',
              'seaborn>=0.11.1',
              'termcolor>=1.1.0',
              'tqdm>=4.60.0',
              'widgetsnbextension>=3.5.1'
          ]
          )
