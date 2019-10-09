import time,os,copy,argparse,subprocess,psutil
import pandas as pd
import numpy as np
import multiprocessing as mp
import tensorflow as tf
from model_architect import *
from utils import *
import generate_pileups as gcp

config = tf.ConfigProto()
config.gpu_options.allow_growth = True

def genotype_caller_skinny(params,input_type='path',data=None,attempt=0,neg_part='neg.combined'):
    tf.reset_default_graph()
    cpu=params['cpu']
    n_input=params['dims']
    chrom_list=params['chrom'].split(':') 
    chrom_list=list(range(int(chrom_list[1]),int(chrom_list[0])-1,-1))
    
    false_mltplr=3
    
    training_iters, learning_rate, batch_size= params['iters'],\
    params['rate'], params['size']

    weights,biases,t1,t2=get_tensors(n_input,learning_rate)
    (x,y,allele,ref,fc_layer,pred,cost,optimizer,cost_gt,cost_allele,keep)=t1
    (correct_prediction, correct_prediction_gt, correct_prediction_allele, accuracy, accuracy_gt, accuracy_allele, gt_likelihood, allele_likelihood)=t2

    if params['val']:
        val_list=[]
        for v_path in params['test_path'].split(':'):
            val_list.append((v_path,get_data_20plus(params)))
        
    
    init = tf.global_variables_initializer()
    saver = tf.train.Saver(max_to_keep=100)
    
    rec_size=1000*(14+n_input[0]*n_input[1]*7)
    
    
    n_size=1
    with tf.Session(config=config)  as sess:
        sess.run(init)
        sess.run(tf.local_variables_initializer())
        if params['retrain']:
            saver.restore(sess, params['model'])        

        stats,v_stats=[],[]
        print('starting training',flush=True)
        count=0
        
        save_num=1
        t=time.time()
        
        iter_ratio=params['ratio'] if params['ratio'] else 20
        
        iter_steps=max(training_iters//iter_ratio,1)
        iters=min(iter_ratio,training_iters)
        
        
        for k in range(iter_steps):
            
            for chrom in chrom_list:
                print('Training on chrom %d ' %(chrom),end='',flush=True)
                
                if chrom<10:
                    chnk=10
                elif chrom<16:
                    chnk=8
                else:
                    chnk=4

                f_path=os.path.join(params['train_path'],'chr%d/chr%d.pileups.' %(chrom,chrom))
                
                tot_list={}
                
                for ftype in ['pos',neg_part]:

                    statinfo = os.stat(f_path+ftype)
                    sz=statinfo.st_size

                    tmp_sz=list(range(0,sz,rec_size*(sz//(chnk*rec_size))))
                    tmp_sz=tmp_sz[:chnk]
                    tmp_sz=tmp_sz+[sz] if tmp_sz[-1]!=sz else tmp_sz
                    tot_list[ftype]=tmp_sz

                for i in range(len(tot_list['pos'])-1):
                    
                    _,x_train,y_train,train_allele,train_ref= get_data(f_path+'pos',a=tot_list['pos'][i], b=tot_list['pos'][i+1], cpu=cpu, dims=n_input)
                    
                    _,nx_train,ny_train,ntrain_allele,ntrain_ref=get_data(f_path+neg_part,a=tot_list[neg_part][i], b=tot_list[neg_part][i+1], cpu=cpu, dims=n_input)
                
                    
                    n_start=-false_mltplr*len(x_train)
                    n_end=0
                    for i in range(iters):

                        n_start+=false_mltplr*len(x_train)
                        n_end=n_start+false_mltplr*len(nx_train)
                        if n_end>len(x_train):
                            n_start=0
                            n_end=n_start+false_mltplr*len(nx_train)
                        batch_nx_train,batch_ny_train,batch_ntrain_allele, batch_ntrain_ref = \
                        nx_train[n_start:n_end,:,:,:],ny_train[n_start:n_end,:],\
                        ntrain_allele[n_start:n_end,:], ntrain_ref[n_start:n_end,:]

                        for batch in range(len(x_train)//batch_size):
                            batch_x = np.vstack([x_train[batch*batch_size:min((batch+1)*batch_size, len(x_train))],\
                                      batch_nx_train[ false_mltplr*batch*batch_size : min(false_mltplr*(batch+1)*batch_size,\
                                      len(batch_nx_train))]])

                            batch_y = np.vstack([y_train[batch*batch_size:min((batch+1)*batch_size, len(y_train))],\
                                      batch_ny_train[false_mltplr*batch*batch_size :min(false_mltplr*(batch+1)*batch_size,\
                                      len(batch_ny_train))]])    
                            batch_ref = np.vstack([train_ref[batch*batch_size :min((batch+1)*batch_size,\
                                        len(train_ref))], batch_ntrain_ref[ false_mltplr*batch*batch_size:\
                                        min(false_mltplr*(batch+1)*batch_size, len(batch_ntrain_ref))]])

                            batch_allele = np.vstack([train_allele[batch*batch_size :min((batch+1)*batch_size,\
                                           len(train_allele))], batch_ntrain_allele[false_mltplr*batch*batch_size : \
                                           min(false_mltplr*(batch+1)*batch_size, len(batch_ntrain_allele))]])
                            # Run optimization op (backprop).
                                # Calculate batch loss and accuracy
                            opt = sess.run(optimizer, feed_dict={x: batch_x,y: batch_y,ref:batch_ref,allele:batch_allele,keep:0.5})

                        #utils.gpu_stats()
                    _,x_train,y_train,train_allele,train_ref= None,None,None,None,None
                    _,nx_train,ny_train,ntrain_allele,ntrain_ref= None,None,None,None,None

                    print('.',end='',flush=True)

                if params['val'] and (k<2 or chrom==1):

                    for val in val_list:
                        print('\n')
                        print(30*'-')
                        print(val[0])
                        vx_test, vy_test, vtest_allele, vtest_ref=val[1]
                        test_stats={'num':0,'acc':0,'gt':0,'allele':0}
                        tp,true,fp=0,0,0
                        loss = sess.run(cost, feed_dict={x: batch_x,y: batch_y, ref:batch_ref, allele:batch_allele, keep:1})
                        for batch in range(len(vx_test)//(batch_size)):
                            vbatch_x = vx_test[batch*batch_size:min((batch+1)*batch_size,len(vx_test))]
                            vbatch_y = vy_test[batch*batch_size:min((batch+1)*batch_size,len(vx_test))] 
                            vbatch_ref = vtest_ref[batch*batch_size:min((batch+1)*batch_size,len(vx_test))]
                            vbatch_allele = vtest_allele[batch*batch_size:min((batch+1)*batch_size,len(vx_test))]


                            fc_layer_batch,score_batch,v_loss,v_acc,v_gt_acc,v_all_acc,prediction = sess.run([fc_layer, pred, cost, accuracy, accuracy_gt, accuracy_allele, correct_prediction], feed_dict={x: vbatch_x,y: vbatch_y,ref:vbatch_ref, allele:vbatch_allele,keep:1.0})

                            mat=np.hstack([prediction[:,np.newaxis], np.argmax(vbatch_y,axis=1)[:,np.newaxis],\
                                       np.argmax(vbatch_ref,axis=1)[:,np.newaxis], np.argmax(vbatch_allele,axis=1)[:,np.newaxis]])
                            tmp=mat[mat[:,2]!=mat[:,3]]
                            tp+=np.sum(tmp[:,0])
                            true+=len(mat[mat[:,2]!=mat[:,3]])
                            tmp=mat[mat[:,2]==mat[:,3]]
                            fp+=(len(mat[mat[:,2]==mat[:,3]])-np.sum(tmp[:,0]))

                            test_stats['num']+=len(vbatch_x)
                            test_stats['acc']+=v_acc
                            test_stats['gt']+=v_gt_acc
                            test_stats['allele']+=v_all_acc


                        print('training loss= %.4f     valid loss= %.4f\n' %(loss, v_loss), flush=True)
                        print('valid accuracy= %.4f' %(test_stats['acc']/test_stats['num']), flush=True)
                        print('valid GT accuracy= %.4f' %(test_stats['gt']/test_stats['num']), flush=True)
                        print('valid Allele accuracy= %.4f' %(test_stats['allele']/test_stats['num']), flush=True)
                        print('validation Precision= %.4f     Validation Recall= %.4f' %(tp/(tp+fp),tp/true), flush=True)
                        print(30*'-')
                        print('\n')

            saver.save(sess, save_path=params['model'],global_step=save_num)
            elapsed=time.time()-t
            
            print ('Time Taken for Iteration %d-%d: %.2f seconds\n'\
                   %((save_num-1)*iters,save_num*iters,elapsed), flush=True)
            
            save_num+=1
            t=time.time()
            
        #saver.save(sess, save_path=params['model'],global_step=save_num)

def test_model(params):
    model_path,test_path,n_input,chrom,vcf_path= params['model'], params['test_path'],params['dims'],params['chrom'],params['vcf_path']
    cpu=params['cpu']
    tf.reset_default_graph()
    
    tr_dim=n_input[:]
    params['window']=None

    weights,biases,t1,t2=get_tensors(tr_dim,1)
    (x,y,allele,ref,fc_layer,pred,cost,optimizer,cost_gt,cost_allele,keep)=t1
    (correct_prediction, correct_prediction_gt, correct_prediction_allele, accuracy, accuracy_gt, accuracy_allele, gt_likelihood, allele_likelihood)=t2
    
    init = tf.global_variables_initializer()
    sess = tf.Session()
    sess.run(init)
    sess.run(tf.local_variables_initializer())
    saver = tf.train.Saver()
    saver.restore(sess, model_path)
    
    rev_mapping={0:'A',1:'G',2:'T',3:'C'}
    gt_map={0:1,1:0}
    rec_size=1000*(12+n_input[0]*n_input[1]*7)
    batch_size=1000
    total=[]
    with open(vcf_path,'w') as f:

        f.write('##fileformat=VCFv4.2\n')
        f.write('##FILTER=<ID=PASS,Description="All filters passed">\n')
        c='##contig=<ID=%s>\n' %chrom
        f.write('##contig=<ID=%s>\n' %chrom)
        

        f.write('##FORMAT=<ID=GT,Number=1,Type=String,Description="Consensus Genotype across all datasets with called genotype">\n')
        f.write('#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO	FORMAT	SAMPLE\n')
        ttt=[]
        
        chnk=1
        tot_list={}
        f_path=params['test_path']
        
        statinfo = os.stat(f_path)
        sz=statinfo.st_size
        tmp_sz=list(range(0,sz,rec_size*(sz//(chnk*rec_size))))
        tmp_sz=tmp_sz[:chnk]
        tmp_sz=tmp_sz+[sz] if tmp_sz[-1]!=sz else tmp_sz

        for i in range(len(tmp_sz)-1):
            
            pos,x_test,_,_,test_ref= get_data(f_path,a=tmp_sz[i], b=tmp_sz[i+1],dims=n_input,cpu=cpu,mode='test')
            for batch in range(len(x_test)//batch_size+1):
                        batch_pos = pos[batch*batch_size:min((batch+1)*batch_size,len(pos))]
                        batch_x = x_test[batch*batch_size:min((batch+1)*batch_size,len(x_test))]

                        batch_ref = test_ref[batch*batch_size:min((batch+1)*batch_size, len(test_ref))]

                        fc_layer_batch,score_batch,gt_like,all_like = sess.run([fc_layer,pred,gt_likelihood,allele_likelihood],\
                                                   feed_dict={x: batch_x,ref:batch_ref,keep:1.0})

                        ref_like=np.max(all_like*batch_ref,axis=1)
                        qual=-10*np.log10(np.abs((gt_like[:,0]-1e-9)))-10*np.log10(np.abs((ref_like-1e-9)))
                        all_pred,gt_pred=np.argmax(fc_layer_batch,axis=1),np.argmax(score_batch,axis=1)

                        
                        mat=np.hstack([batch_pos,np.argmax(batch_ref,axis=1)[:,np.newaxis],\
                                   all_pred[:,np.newaxis],gt_pred[:,np.newaxis],qual[:,np.newaxis]])
                        total.append(mat)
                        mat=mat[(mat[:,1]!=mat[:,2])]
                        for j in range(len(mat)):

                            v=mat[j]

                            s='%s\t%d\t.\t%s\t%s\t%d\t%s\t.\tGT\t1/%d\n' %\
                            (chrom,v[0],rev_mapping[v[1]],rev_mapping[v[2]],v[4],'PASS',gt_map[v[3]])

                            f.write(s)
    return
                    
def test_model_no_pileups(params):
    chrom_length={'chr1':248956422, 'chr2':242193529, 'chr3':198295559, 'chr4':190214555, 'chr5':181538259, 'chr6':170805979, \
             'chr7':159345973, 'chr8':145138636, 'chr9':138394717, 'chr10':133797422, 'chr11':135086622, 'chr12':133275309,\
             'chr13':114364328, 'chr14':107043718, 'chr15':101991189, 'chr16':90338345, 'chr17':83257441, 'chr18':80373285,\
             'chr19':58617616, 'chr20':64444167, 'chr21':46709983, 'chr22':50818468, 'chrX':156040895, 'chrY':57227415}
    
    
    model_path,n_input,vcf_path= params['model'],params['dims'],params['vcf_path']
    cpu=params['cpu']
    
    if len(args.region.split(':'))==2:
        chrom,region=args.region.split(':')
        start,end=int(region.split('-')[0]),int(region.split('-')[1])
        
    else:
        chrom=args.region.split(':')[0]
        start,end=1,chrom_length[chrom]
   
    params['chrom']=chrom 
    
    tf.reset_default_graph()
    
    tr_dim=n_input[:]
    params['window']=None

    weights,biases,t1,t2=get_tensors(tr_dim,1)
    (x,y,allele,ref,fc_layer,pred,cost,optimizer,cost_gt,cost_allele,keep)=t1
    (correct_prediction, correct_prediction_gt, correct_prediction_allele, accuracy, accuracy_gt, accuracy_allele, gt_likelihood, allele_likelihood)=t2
    
    init = tf.global_variables_initializer()
    sess = tf.Session()
    sess.run(init)
    sess.run(tf.local_variables_initializer())
    saver = tf.train.Saver()
    saver.restore(sess, model_path)
    
    rev_mapping={0:'A',1:'G',2:'T',3:'C'}
    gt_map={0:1,1:0}
    rec_size=1000*(12+n_input[0]*n_input[1]*7)
    batch_size=1000
    total=[]
    with open(vcf_path,'w') as f:

        f.write('##fileformat=VCFv4.2\n')
        f.write('##FILTER=<ID=PASS,Description="All filters passed">\n')
        c='##contig=<ID=%s>\n' %chrom
        f.write('##contig=<ID=%s>\n' %chrom)
        

        f.write('##FORMAT=<ID=GT,Number=1,Type=String,Description="Consensus Genotype across all datasets with called genotype">\n')
        f.write('#CHROM	POS	ID	REF	ALT	QUAL	FILTER	INFO	FORMAT	SAMPLE\n')
        ttt=[]
        
        chunks=list(range(start,end,int(1e6)))+[end]
        
        for i in range(len(chunks)-1):
            d = copy.deepcopy(params)
            d['start']=chunks[i]
            d['end']=chunks[i]
            d['chrom']=chrom

            pos,x_test,test_ref= gcp.generate(d)
            
            if len(pos)==0:
              continue
            for batch in range(len(x_test)//batch_size+1):
                        batch_pos = pos[batch*batch_size:min((batch+1)*batch_size,len(pos))]
                        batch_x = x_test[batch*batch_size:min((batch+1)*batch_size,len(x_test))]

                        batch_ref = test_ref[batch*batch_size:min((batch+1)*batch_size, len(test_ref))]

                        fc_layer_batch,score_batch,gt_like,all_like = sess.run([fc_layer,pred,gt_likelihood,allele_likelihood],\
                                                   feed_dict={x: batch_x,ref:batch_ref,keep:1.0})

                        ref_like=np.max(all_like*batch_ref,axis=1)
                        qual=-10*np.log10(np.abs((gt_like[:,0]-1e-9)))-10*np.log10(np.abs((ref_like-1e-9)))
                        all_pred,gt_pred=np.argmax(fc_layer_batch,axis=1),np.argmax(score_batch,axis=1)

                        
                        mat=np.hstack([batch_pos,np.argmax(batch_ref,axis=1)[:,np.newaxis],\
                                   all_pred[:,np.newaxis],gt_pred[:,np.newaxis],qual[:,np.newaxis]])
                        total.append(mat)
                        mat=mat[(mat[:,1]!=mat[:,2])]
                        for j in range(len(mat)):

                            v=mat[j]

                            s='%s\t%d\t.\t%s\t%s\t%d\t%s\t.\tGT\t1/%d\n' %\
                            (chrom,v[0],rev_mapping[v[1]],rev_mapping[v[2]],v[4],'PASS',gt_map[v[3]])

                            f.write(s)
    return

def test_model_novcf(params,input_type='path',data=None):
    tf.reset_default_graph()
    cpu=params['cpu']
    n_input=params['dims']
    if input_type=='path':
        vx_test,vy_test,vtest_allele,vtest_ref=get_train_test(params,mode='test')
    else:
        vx_test,vy_test,vtest_allele,vtest_ref=data['test_data']
        
    training_iters, learning_rate,model_path= params['iters'],\
    params['rate'], params['model']

    weights,biases,t1,t2=get_tensors(n_input,1)
    (x,y,allele,ref,fc_layer,pred,cost,optimizer,cost_gt,cost_allele,keep)=t1
    (correct_prediction, correct_prediction_gt, correct_prediction_allele, accuracy, accuracy_gt, accuracy_allele, gt_likelihood, allele_likelihood)=t2
    
    init = tf.global_variables_initializer()
    sess = tf.Session()
    sess.run(init)
    sess.run(tf.local_variables_initializer())
    saver = tf.train.Saver()
    saver.restore(sess, model_path)
    
    batch_size=1000
    tp,fp,true=0,0,0
    test_stats={'num':0,'acc':0,'gt':0,'allele':0}
    for batch in range(len(vx_test)//(batch_size)):
        vbatch_x = vx_test[batch*batch_size:min((batch+1)*batch_size,len(vx_test))]
        vbatch_y = vy_test[batch*batch_size:min((batch+1)*batch_size,len(vx_test))] 
        vbatch_ref = vtest_ref[batch*batch_size:min((batch+1)*batch_size,len(vx_test))]
        vbatch_allele = vtest_allele[batch*batch_size:min((batch+1)*batch_size,len(vx_test))]

        fc_layer_batch,score_batch,v_loss,v_acc,v_gt_acc,v_all_acc,prediction = sess.run([fc_layer, pred, cost, accuracy, accuracy_gt, accuracy_allele, correct_prediction], feed_dict={x: vbatch_x,y: vbatch_y,ref:vbatch_ref, allele:vbatch_allele,keep:1.0})

        mat=np.hstack([prediction[:,np.newaxis], np.argmax(vbatch_y,axis=1)[:,np.newaxis],\
                   np.argmax(vbatch_ref,axis=1)[:,np.newaxis], np.argmax(vbatch_allele,axis=1)[:,np.newaxis]])
        tmp=mat[mat[:,2]!=mat[:,3]]
        tp+=np.sum(tmp[:,0])
        true+=len(mat[mat[:,2]!=mat[:,3]])
        tmp=mat[mat[:,2]==mat[:,3]]
        fp+=(len(mat[mat[:,2]==mat[:,3]])-np.sum(tmp[:,0]))

        test_stats['num']+=len(vbatch_x)
        test_stats['acc']+=v_acc
        test_stats['gt']+=v_gt_acc
        test_stats['allele']+=v_all_acc

    print(100*'.')
    print('valid loss= %.4f\n' %( v_loss), flush=True)
    print('valid accuracy= %.4f' %(test_stats['acc']/test_stats['num']), flush=True)
    print('valid GT accuracy= %.4f' %(test_stats['gt']/test_stats['num']), flush=True)
    print('valid Allele accuracy= %.4f' %(test_stats['allele']/test_stats['num']), flush=True)
    print(' Validation Precision= %.4f     Validation Recall= %.4f' %(tp/(tp+fp),tp/true), flush=True)
    print(100*'.')
    print('\n')

   
def get_data_20plus(params):
    dims=params['dims']
    rec_size=14+dims[0]*dims[1]*7
    cpu=params['cpu']
    n_input=params['dims']
    f_path=params['test_path']
    _,vpx_train,vpy_train,vptrain_allele,vptrain_ref= get_data(f_path+'pos',cpu=cpu,dims=n_input,a=5000*rec_size,b=20000*rec_size)
    _,vnx_test,vny_test,vntest_allele,vntest_ref=get_data(f_path+'neg.combined.20plus',cpu=cpu,dims=n_input,a=5000*rec_size,b=20000*rec_size)
    vx_test,vy_test,vtest_allele,vtest_ref =np.vstack([vpx_train,vnx_test]), np.vstack([vpy_train,vny_test]), np.vstack([vptrain_allele,vntest_allele]), np.vstack([vptrain_ref,vntest_ref])
    return (vx_test,vy_test,vtest_allele,vtest_ref)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-r", "--rate", help="Learning rate",type=float)
    parser.add_argument("-i", "--iterations", help="Training iterations",type=int)
    parser.add_argument("-s", "--size", help="Batch size",type=int)
    parser.add_argument("-train", "--train", help="Train path")
    parser.add_argument("-test", "--test", help="Test path")
    parser.add_argument("-model", "--model", help="Model output path")
    parser.add_argument("-m", "--mode", help="Mode")
    parser.add_argument("-dim", "--dimensions", help="Input dimensions")
    parser.add_argument("-vcf", "--vcf", help="VCF output path")
    parser.add_argument("-cpu", "--cpu", help="CPUs",type=int)
    parser.add_argument("-val", "--validation", help="Validation",type=int)
    parser.add_argument("-rt", "--retrain", help="Retrain saved model",type=int)
    parser.add_argument("-w", "--window", help="Window size around site",type=int)
    parser.add_argument("-ratio", "--ratio", help="iterations per batch",type=int)
    parser.add_argument("-neg", "--neg_part", help="Negative Part")
    parser.add_argument("-chrom", "--chrom", help="Chromosome") 
    parser.add_argument("-region", "--region", help="Chromosome region")
    parser.add_argument("-bam", "--bam", help="Bam file")
    parser.add_argument("-ref", "--ref", help="Size")
    parser.add_argument("-d", "--depth", help="Depth",type=int)
    parser.add_argument("-t", "--threshold", help="Threshold",type=float)
    parser.add_argument("-bed", "--bed", help="BED file")
    parser.add_argument("-mincov", "--mincov", help="min coverage",type=int)
    
    
    
    args = parser.parse_args()
    input_dims=[int(x) for x in args.dimensions.split(':')]
    t=time.time()
    
    if args.mode=='train':
        in_dict={'cpu':args.cpu,'rate':args.rate, 'iters':args.iterations, 'size':args.size,'dims':input_dims,'chrom':args.chrom,\
                 'train_path':args.train, 'test_path':args.test, 'model':args.model, 'val':args.validation,'retrain':args.retrain,\
                'window':args.window,'ratio':args.ratio}
        genotype_caller_skinny(in_dict,neg_part=args.neg_part)
    
    
    elif args.mode=='direct':
        in_dict={'cpu':args.cpu,'mode':args.mode,'dims':input_dims,'test_path':args.test,'model':args.model,'chrom':args.chrom,'vcf_path':args.vcf, 'region':args.region,'bam':args.bam,'ref':args.ref,'threshold':args.threshold,'bed':args.bed,'mincov':args.mincov}
        test_model_no_pileups(in_dict)
    else:
        in_dict={'cpu':args.cpu,'dims':input_dims,'test_path':args.test,'model':args.model,'chrom':args.chrom,'vcf_path':args.vcf, 'region':args.region,'bam':args.bam,'ref':args.ref,'threshold':args.threshold,'bed':args.bed,'mincov':args.mincov}
        test_model(in_dict)
        
    elapsed=time.time()-t
    print ('Total Time Elapsed: %.2f seconds' %elapsed)