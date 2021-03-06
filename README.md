# NanoCaller
NanoCaller is a computational method that integrates long reads in deep convolutional neural network for the detection of SNPs/indels from long-read sequencing data. NanoCaller uses long-range haplotype structure to generate predictions for each SNP candidate variant site by considering pileup information of other candidate sites sharing reads. Subsequently, it performs read phasing, and carries out local realignment of each set of phased reads and the set of all reads for each indel candidate variant site to generate indel calling, and then creates consensus sequences for indel sequence prediction.

## Citing NanoCaller
Please cite: Ahsan, Umair and Liu, Qian and Wang, Kai. NanoCaller for accurate detection of SNPs and small indels from long-read sequencing by deep neural networks. bioRxiv 2019.12.29.890418; doi: https://doi.org/10.1101/2019.12.29.890418

## Installation
NanoCaller has been developed and tested to work with Linux OS; we do not recommend using Windows or Mac OS. NanoCaller does not require a GPU or any other special hardware to run.

First, install Miniconda, a minimal installation of Anaconda, which is much smaller and has a faster installation.
Note that this version is meant for Linux below, macOS and Windows have a different script:

```
curl -O https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
```

Go through all the prompts (installation in `$HOME` is recommended). After Anaconda is installed successfully, simply run:

```
git clone https://github.com/WGLab/NanoCaller.git
cd NanoCaller
conda env create -f environment.yml
conda activate NanoCaller
```
The installation should take about 10 minutes, including the installation of Miniconda.

## Usage
```
python PATH_TO_NANOCALLER_REPOSITORY/scripts/NanoCaller.py [-h]
		     -bam BAM -ref REF -prefix PREFIX
		     [-mode MODE] [-seq SEQUENCING] [-model MODEL]
                     [-vcf VCF] [-chrom CHROM] [-cpu CPU]
                     [-min_allele_freq MIN_ALLELE_FREQ]
                     [-min_nbr_sites MIN_NBR_SITES]  [-sample SAMPLE] 
		     [-sup] [-mincov MINCOV] [-maxcov MAXCOV] 
		     [-start START] [-end END]
                     [-nbr_t NEIGHBOR_THRESHOLD] [-ins_t INS_THRESHOLD]
                     [-del_t DEL_THRESHOLD] [-disable_whatshap]
                     [-wgs_print_commands]
                     [-wgs_contigs_type WGS_CONTIGS_TYPE]

Required arguments:
  -bam BAM, --bam BAM   Bam file, should be phased if 'indel' mode is selected
                        (default: None)
  -ref REF, --ref REF   reference genome file with .fai index (default: None)
  -prefix PREFIX, --prefix PREFIX
                        VCF file prefix (default: None)
			
optional arguments:
  -h, --help            show this help message and exit
  -mode MODE, --mode MODE
                        Testing mode, options are 'snps', 'indels' and 'both'
                        (default: both)
  -seq SEQUENCING, --sequencing SEQUENCING
                        Sequencing type, options are 'ont' and 'pacbio'
                        (default: ont)
  -model MODEL, --model MODEL
                        NanoCaller SNP model to be used, options are
                        'NanoCaller1' (trained on HG001 Nanopore reads),
                        'NanoCaller2' (trained on HG002 Nanopore reads) and
                        'NanoCaller3' (trained on HG003 PacBio reads)
                        (default: NanoCaller1)
  -vcf VCF, --vcf VCF   VCF output path, default is current working directory
                        (default: None)
  -chrom CHROM, --chrom CHROM
                        Chromosome (default: None)
  -cpu CPU, --cpu CPU   CPUs (default: 1)
  -min_allele_freq MIN_ALLELE_FREQ, --min_allele_freq MIN_ALLELE_FREQ
                        minimum alternative allele frequency (default: 0.15)
  -min_nbr_sites MIN_NBR_SITES, --min_nbr_sites MIN_NBR_SITES
                        minimum number of nbr sites (default: 1)
  -sample SAMPLE, --sample SAMPLE
                        VCF file sample name (default: SAMPLE)
  -sup, --supplementary
                        Use supplementary reads (default: False)
  -mincov MINCOV, --mincov MINCOV
                        min coverage (default: 8)
  -maxcov MAXCOV, --maxcov MAXCOV
                        max coverage (default: 160)
  -start START, --start START
                        start, default is 1 (default: None)
  -end END, --end END   end, default is the end of contig (default: None)
  -nbr_t NEIGHBOR_THRESHOLD, --neighbor_threshold NEIGHBOR_THRESHOLD
                        SNP neighboring site thresholds with lower and upper
                        bounds seperated by comma, for Nanopore reads
                        '0.4,0.6' is recommended and for PacBio reads
                        '0.3,0.7' is recommended (default: 0.4,0.6)
  -ins_t INS_THRESHOLD, --ins_threshold INS_THRESHOLD
                        Insertion Threshold (default: 0.4)
  -del_t DEL_THRESHOLD, --del_threshold DEL_THRESHOLD
                        Deletion Threshold (default: 0.6)
  -disable_whatshap, --disable_whatshap
                        Allow WhatsHap to change SNP genotypes when phasing
                        (default: False)
  -wgs_print_commands, --wgs_print_commands
                        If set, print the commands to run NanoCaller on all
                        contigs in a file named "wg_commands". By default, run
                        the NanoCaller on each contig in a sequence. (default:
                        False)
  -wgs_contigs_type WGS_CONTIGS_TYPE, --wgs_contigs_type WGS_CONTIGS_TYPE
                        Options are "with_chr", "without_chr" and "all", or a
                        space/whitespace separated list of contigs in
                        quotation marks e.g. "chr3 chr6 chr22" . "with_chr"
                        option will assume human genome and run NanoCaller on
                        chr1-22, "without_chr" will run on chromosomes 1-22 if
                        the BAM and reference genome files use chromosome
                        names without "chr". "all" option will run NanoCaller
                        on each contig present in reference genome FASTA file.
                        (default: with_chr)


		     

```
## Example
An example of NanoCaller usage is provided in [sample](sample). The results are stored in [test output](sample/test_run) and were created using the following command:

`python ../scripts/NanoCaller.py -bam HG002.nanopore.chr22.sample.bam -mode both -seq ont -model NanoCaller1 -vcf test_run -chrom chr22 -start 20000000 -end 21000000 -ref chr22_ref.fa -prefix HG002.chr22.sample -cpu 1 > log`

which is also in the file [sample_call](sample/sample_call). This example should take about 10-15 minutes to run.
