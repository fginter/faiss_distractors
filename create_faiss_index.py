import faiss
import torch
import glob
import random
import tqdm

def random_sample_of_batches(batch_files,proportion):
    """Takes a random sample of batches from all batch_files
    this is used to make training data for faiss. Proportion is from [0,1] interval"""
    all_batches=[]
    batch_files=list(batch_files)
    random.shuffle(batch_files)
    for b in tqdm.tqdm(batch_files):
        batches=torch.load(b)
        random.shuffle(batches)
        batches=batches[:int(len(batches)*proportion)]
        all_batches.extend(batches)
    return torch.vstack(all_batches)

if __name__=="__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("BATCHFILES",default=None,nargs="+",help="Batch files saved by embed.py")
    parser.add_argument("--prepare-sample",default=None,help="File name to save the sampled examples to. Prepares sample from batchfiles on which faiss can be trained. Does a 5% sample by default.")
    parser.add_argument("--train-faiss",default=None,help="File name to save the trained faiss index to. BATCHFILES should be a single .pt produced by --prepare-sample")
    parser.add_argument("--fill-faiss",default=None,help="Fill faiss index with vectors and save to index with the name given i this argument. BATCHFILES are all batchfiles to store into the index (will be sorted by name). Give the name of the trained index (trained with --train-faiss) in the argument --pretrained-index")
    parser.add_argument("--pretrained-index",default=None,help="Name of the pretrained index to be used for --fill-fais")
    args = parser.parse_args()


    if args.prepare_sample:
        sampled=random_sample_of_batches(sorted(args.BATCHFILES),0.05)
        torch.save(sampled,args.prepare_sample)
    elif args.train_faiss:
        assert len(args.BATCHFILES)==1, "Give one argument which is a .pt file produced by --prepare-sample"

        quantizer=faiss.IndexFlatL2(768)
        index=faiss.IndexIVFPQ(quantizer,768,1024,48,8) #768 is bert size, 1024 is how many Voronoi cells we want, 48 is number of quantizers, and these are 8-bit
        res=faiss.StandardGpuResources()
        index_gpu=faiss.index_cpu_to_gpu(res,0,index)

        sampled_vectors=torch.load(args.BATCHFILES[0])
        print("Training on",sampled_vectors.shape,"vectors",flush=True)

        index_gpu.train(sampled_vectors.numpy()) #how comes this doesnt take any time at all ...?
        print("Done training",flush=True)
        trained_index=faiss.index_gpu_to_cpu(index_gpu)
        faiss.write_index(trained_index,args.train_faiss)
    elif args.fill_faiss:
        index=faiss.read_index(args.pretrained_index)
        res=faiss.StandardGpuResources()
        index_gpu=faiss.index_cpu_to_gpu(res,0,index)
        all_batches=list(sorted(args.BATCHFILES)) #THESE MUST BE SORTED BY FILENAME OR ELSE STUFF GOES OUT OF ORDER!
        for batchfile in tqdm.tqdm(all_batches):
            batches=torch.load(batchfile)
            all_vectors=torch.vstack(batches)
            index_gpu.add(all_vectors.numpy())
        index_filled=faiss.index_gpu_to_cpu(index_gpu)
        faiss.write_index(index_filled,args.fill_faiss)
        print("Index has",index_filled.ntotal,"vectors. Done.")

