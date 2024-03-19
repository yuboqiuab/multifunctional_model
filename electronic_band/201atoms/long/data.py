import csv
import functools
import json, gzip
import torch, os
import zlib
import math
from pathlib import Path
import os.path as osp

from itertools import product

import numpy as np
from numpy.linalg import norm
from pymatgen.core.structure import Structure
from pymatgen.core.bonds import CovalentBond
from pymatgen.core.lattice import Lattice
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer
import torch.nn.functional as F
from torch.utils.data import Dataset
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader as GraphDataLoader
import matplotlib.pyplot as plt
from torch.utils.data.dataset import random_split, Subset

from multiprocessing import Pool
from tqdm import tqdm


PATH = Path(__file__).parent





class CrystalGraphDataset(Dataset):
    def __init__(self, dataset_dir, dataset_ratio=1.0, radius=8.0, n_nbr=18):
        super().__init__()

        self.radius = radius
        self.n_nbr = n_nbr
        self.struc_dir = osp.join(dataset_dir, 'structures')
        self.ham_dir = osp.join(dataset_dir, 'hamiltonians')
        self.ids = os.listdir(self.struc_dir)
        self.ids = self.ids[:int(len(self.ids) * dataset_ratio)]


    def __len__(self):
        return len(self.ids)

    @functools.lru_cache(maxsize=None)
    def __getitem__(self, index):

        file = osp.join(self.struc_dir, self.ids[index])
        fid = self.ids[index].split('_')[1]
        with open(file, 'r') as f:
            cont = f.read()
        struc = Structure.from_str(cont, fmt='poscar')
        h_file = osp.join(self.ham_dir, 'hamiltonians_{}'.format(fid))
        hoppings = []
        with open(h_file, 'r') as f:
            for line in f:
                hoppings.append(float(line.split()[-2]))
        hoppings = np.array(hoppings)

        self._get_edge_and_face(struc,hoppings,fid)


    def _get_edge_and_face(self, struc, hoppings,fid):
        vect1=[]
        with open('part1', 'r') as f:
             for row in f:
                vect1.append(row.split())
        vect1 = (np.array(vect1)).astype(np.float64)

        vect2=[]
        with open('part2', 'r') as f:
             for row in f:
                vect2.append(row.split())
        vect2 = (np.array(vect2)).astype(np.float64)

        vect3=[]
        with open('part3', 'r') as f:
             for row in f:
                vect3.append(row.split())
        vect3 = (np.array(vect3)).astype(np.float64)

        vect4=-vect1
        vect5=-vect2
        vect6=-vect3

        m=struc.lattice.matrix
        lattice=Lattice(struc.lattice.matrix)
        num=struc.num_sites
        nw=int(num/3*5+num/3*2*3)
        atom=[]
        ave1=0
        for i in range(num):
            atom.append(struc.frac_coords[i])
            ave1=ave1+struc.frac_coords[i][2]
        ave1=ave1/(num*1.0)
        ave2=0
        ave3=0
        num2=0
        num3=0
        for i in range(num):
            if(atom[i][2]<ave1):
                num2=num2+1
                ave2=ave2+atom[i][2]
            if(atom[i][2]>ave1):
                num3=num3+1
                ave3=ave3+atom[i][2]
        ave2=ave2/(num2*1.0)
        ave3=ave3/(num3*1.0)
        flag= np.zeros(num,dtype='int')

        c,d = [],[]
        for i in range(num):
            if((i<int(num/3)) and (atom[i][2])<ave1):
               a,b = self._get_list1(struc, vect1, atom[i])
            if((i<int(num/3)) and (atom[i][2])>ave1):
               a,b = self._get_list1(struc, vect4, atom[i])
            if((i>=int(num/3)) and (atom[i][2])<ave1 and (atom[i][2])>ave2):
               a,b = self._get_list2(struc, vect2, atom[i])
            if((i>=int(num/3)) and (atom[i][2])<ave1 and (atom[i][2])<ave2):
               a,b = self._get_list2(struc, vect3, atom[i])
            if((i>=int(num/3)) and (atom[i][2])>ave1 and (atom[i][2])>ave3):
               a,b = self._get_list2(struc, vect6, atom[i])
            if((i>=int(num/3)) and (atom[i][2])>ave1 and (atom[i][2])<ave3):
               a,b = self._get_list2(struc, vect5, atom[i])
            c.append(a)
            d.append(b)


        for i in range(num):
            if((i<int(num/3)) and (atom[i][2])<ave1):
                flag[i]=0
                temp_r = 1000.0
                for j in range(int(num/3)):
                    if(atom[j][2]>ave1):
                        a,b = lattice.get_distance_and_image(atom[i],atom[j])
                    else:
                        a = 1000.0
                    if(a<temp_r):
                        temp_r=a
                        temp_image=b
                        temp_j=j
                a,b = self._get_list1(struc, vect4, atom[temp_j])
                dis=lattice.get_cartesian_coords(atom[temp_j]+temp_image-atom[i])
                add=np.zeros(4,dtype='float')
                new=np.zeros(4,dtype='float')
                rad=dis[0]*dis[0]+dis[1]*dis[1]+dis[2]*dis[2];
                add[0]=1.0/np.sqrt(rad)
                add[1]=dis[0]/rad
                add[2]=dis[1]/rad
                add[3]=dis[2]/rad
                c[i].append(add)
                for k in range(len(a)):
                    add=np.zeros(4,dtype='float')
                    new=np.zeros(4,dtype='float')
                    add[0]=(a[k][1]/a[k][0]/a[k][0]+dis[0])
                    add[1]=(a[k][2]/a[k][0]/a[k][0]+dis[1])
                    add[2]=(a[k][3]/a[k][0]/a[k][0]+dis[2])
                    rad=add[0]*add[0]+add[1]*add[1]+add[2]*add[2];
                    new[0]=1.0/np.sqrt(rad)
                    new[1]=add[0]/rad
                    new[2]=add[1]/rad
                    new[3]=add[2]/rad
                    c[i].append(new)

            if((i<int(num/3)) and (atom[i][2])>ave1):
                flag[i]=1
                temp_r = 1000.0
                for j in range(int(num/3)):
                    if(atom[j][2]<ave1):
                        a,b = lattice.get_distance_and_image(atom[i],atom[j])
                    else:
                        a = 1000.0
                    if(a<temp_r):
                        temp_r=a
                        temp_image=b
                        temp_j=j
                a,b = self._get_list1(struc, vect1, atom[temp_j])
                dis=lattice.get_cartesian_coords(atom[temp_j]+temp_image-atom[i])
                add=np.zeros(4,dtype='float')
                new=np.zeros(4,dtype='float')
                rad=dis[0]*dis[0]+dis[1]*dis[1]+dis[2]*dis[2];
                add[0]=1.0/np.sqrt(rad)
                add[1]=dis[0]/rad
                add[2]=dis[1]/rad
                add[3]=dis[2]/rad
                c[i].append(add)
                for k in range(len(a)):
                    add=np.zeros(4,dtype='float')
                    new=np.zeros(4,dtype='float')
                    add[0]=(a[k][1]/a[k][0]/a[k][0]+dis[0])
                    add[1]=(a[k][2]/a[k][0]/a[k][0]+dis[1])
                    add[2]=(a[k][3]/a[k][0]/a[k][0]+dis[2])
                    rad=add[0]*add[0]+add[1]*add[1]+add[2]*add[2];
                    new[0]=1.0/np.sqrt(rad)
                    new[1]=add[0]/rad
                    new[2]=add[1]/rad
                    new[3]=add[2]/rad
                    c[i].append(new)


            if((i>=int(num/3)) and (atom[i][2])<ave1 and (atom[i][2])>ave2):
                flag[i]=0
                temp_r = 1000.0
                for j in range(int(num/3),num):
                    if(atom[j][2]>ave1 and atom[j][2]<ave3):
                        a,b = lattice.get_distance_and_image(atom[i],atom[j])
                    else:
                        a = 1000.0
                    if(a<temp_r):
                        temp_r=a
                        temp_image=b
                        temp_j=j
                a,b = self._get_list2(struc, vect5, atom[temp_j])
                dis=lattice.get_cartesian_coords(atom[temp_j]+temp_image-atom[i])
                add=np.zeros(4,dtype='float')
                new=np.zeros(4,dtype='float')
                rad=dis[0]*dis[0]+dis[1]*dis[1]+dis[2]*dis[2];
                add[0]=1.0/np.sqrt(rad)
                add[1]=dis[0]/rad
                add[2]=dis[1]/rad
                add[3]=dis[2]/rad
                c[i].append(add)
                for k in range(len(a)):
                    add=np.zeros(4,dtype='float')
                    new=np.zeros(4,dtype='float')
                    add[0]=(a[k][1]/a[k][0]/a[k][0]+dis[0])
                    add[1]=(a[k][2]/a[k][0]/a[k][0]+dis[1])
                    add[2]=(a[k][3]/a[k][0]/a[k][0]+dis[2])
                    rad=add[0]*add[0]+add[1]*add[1]+add[2]*add[2];
                    new[0]=1.0/np.sqrt(rad)
                    new[1]=add[0]/rad
                    new[2]=add[1]/rad
                    new[3]=add[2]/rad
                    c[i].append(new)

            if((i>=int(num/3)) and (atom[i][2])<ave1 and (atom[i][2])<ave2):
                flag[i]=0
                temp_r = 1000.0
                for j in range(int(num/3),num):
                    if(atom[j][2]>ave1 and atom[j][2]<ave3):
                        a,b = lattice.get_distance_and_image(atom[i],atom[j])
                    else:
                        a = 1000.0
                    if(a<temp_r):
                        temp_r=a
                        temp_image=b
                        temp_j=j
                a,b = self._get_list2(struc, vect5, atom[temp_j])
                dis=lattice.get_cartesian_coords(atom[temp_j]+temp_image-atom[i])
                add=np.zeros(4,dtype='float')
                new=np.zeros(4,dtype='float')
                rad=dis[0]*dis[0]+dis[1]*dis[1]+dis[2]*dis[2];
                add[0]=1.0/np.sqrt(rad)
                add[1]=dis[0]/rad
                add[2]=dis[1]/rad
                add[3]=dis[2]/rad
                c[i].append(add)
                for k in range(len(a)):
                    add=np.zeros(4,dtype='float')
                    new=np.zeros(4,dtype='float')
                    add[0]=(a[k][1]/a[k][0]/a[k][0]+dis[0])
                    add[1]=(a[k][2]/a[k][0]/a[k][0]+dis[1])
                    add[2]=(a[k][3]/a[k][0]/a[k][0]+dis[2])
                    rad=add[0]*add[0]+add[1]*add[1]+add[2]*add[2];
                    new[0]=1.0/np.sqrt(rad)
                    new[1]=add[0]/rad
                    new[2]=add[1]/rad
                    new[3]=add[2]/rad
                    c[i].append(new)


            if((i>=int(num/3)) and (atom[i][2])>ave1 and (atom[i][2])>ave3):
                flag[i]=1
                temp_r = 1000.0
                for j in range(int(num/3),num):
                    if(atom[j][2]<ave1 and atom[j][2]>ave2):
                        a,b = lattice.get_distance_and_image(atom[i],atom[j])
                    else:
                        a = 1000.0
                    if(a<temp_r):
                        temp_r=a
                        temp_image=b
                        temp_j=j
                a,b = self._get_list2(struc, vect2, atom[temp_j])
                dis=lattice.get_cartesian_coords(atom[temp_j]+temp_image-atom[i])
                add=np.zeros(4,dtype='float')
                new=np.zeros(4,dtype='float')
                rad=dis[0]*dis[0]+dis[1]*dis[1]+dis[2]*dis[2];
                add[0]=1.0/np.sqrt(rad)
                add[1]=dis[0]/rad
                add[2]=dis[1]/rad
                add[3]=dis[2]/rad
                c[i].append(add)
                for k in range(len(a)):
                    add=np.zeros(4,dtype='float')
                    new=np.zeros(4,dtype='float')
                    add[0]=(a[k][1]/a[k][0]/a[k][0]+dis[0])
                    add[1]=(a[k][2]/a[k][0]/a[k][0]+dis[1])
                    add[2]=(a[k][3]/a[k][0]/a[k][0]+dis[2])
                    rad=add[0]*add[0]+add[1]*add[1]+add[2]*add[2];
                    new[0]=1.0/np.sqrt(rad)
                    new[1]=add[0]/rad
                    new[2]=add[1]/rad
                    new[3]=add[2]/rad
                    c[i].append(new)

            if((i>=int(num/3)) and (atom[i][2])>ave1 and (atom[i][2])<ave3):
                flag[i]=1
                temp_r = 1000.0
                for j in range(int(num/3),num):
                    if(atom[j][2]<ave1 and atom[j][2]>ave2):
                        a,b = lattice.get_distance_and_image(atom[i],atom[j])
                    else:
                        a = 1000.0
                    if(a<temp_r):
                        temp_r=a
                        temp_image=b
                        temp_j=j
                a,b = self._get_list2(struc, vect2, atom[temp_j])
                dis=lattice.get_cartesian_coords(atom[temp_j]+temp_image-atom[i])
                add=np.zeros(4,dtype='float')
                new=np.zeros(4,dtype='float')
                rad=dis[0]*dis[0]+dis[1]*dis[1]+dis[2]*dis[2];
                add[0]=1.0/np.sqrt(rad)
                add[1]=dis[0]/rad
                add[2]=dis[1]/rad
                add[3]=dis[2]/rad
                c[i].append(add)
                for k in range(len(a)):
                    add=np.zeros(4,dtype='float')
                    new=np.zeros(4,dtype='float')
                    add[0]=(a[k][1]/a[k][0]/a[k][0]+dis[0])
                    add[1]=(a[k][2]/a[k][0]/a[k][0]+dis[1])
                    add[2]=(a[k][3]/a[k][0]/a[k][0]+dis[2])
                    rad=add[0]*add[0]+add[1]*add[1]+add[2]*add[2];
                    new[0]=1.0/np.sqrt(rad)
                    new[1]=add[0]/rad
                    new[2]=add[1]/rad
                    new[3]=add[2]/rad
                    c[i].append(new)

        f11 = open('inputmm1m_'+fid, 'w');
        f12 = open('inputmm2m_'+fid, 'w');
        f13 = open('outputmm_'+fid, 'w');
        f14 = open('vectormm_'+fid,'w')
        f15 = open('indexmm_'+fid,'w')

        f21 = open('inputms1m_'+fid, 'w');
        f22 = open('inputms2s_'+fid, 'w');
        f23 = open('outputms_'+fid, 'w');
        f24 = open('vectorms_'+fid,'w')
        f25 = open('indexms_'+fid,'w')

        f31 = open('inputsm1s_'+fid, 'w');
        f32 = open('inputsm2m_'+fid, 'w');
        f33 = open('outputsm_'+fid, 'w');
        f34 = open('vectorsm_'+fid,'w')
        f35 = open('indexsm_'+fid,'w')        

        f41 = open('inputss1s_'+fid, 'w');
        f42 = open('inputss2s_'+fid, 'w');
        f43 = open('outputss_'+fid, 'w');
        f44 = open('vectorss_'+fid,'w')
        f45 = open('indexss_'+fid,'w')

        f51 = open('inputmm1mgap_'+fid, 'w');
        f52 = open('inputmm2mgap_'+fid, 'w');
        f53 = open('outputmmgap_'+fid, 'w');
        f54 = open('vectormmgap_'+fid,'w')
        f55 = open('indexmmgap_'+fid,'w')

        f61 = open('inputms1mgap_'+fid, 'w');
        f62 = open('inputms2sgap_'+fid, 'w');
        f63 = open('outputmsgap_'+fid, 'w');
        f64 = open('vectormsgap_'+fid,'w')
        f65 = open('indexmsgap_'+fid,'w')

        f71 = open('inputsm1sgap_'+fid, 'w');
        f72 = open('inputsm2mgap_'+fid, 'w');
        f73 = open('outputsmgap_'+fid, 'w');
        f74 = open('vectorsmgap_'+fid,'w')
        f75 = open('indexsmgap_'+fid,'w')

        f81 = open('inputss1sgap_'+fid, 'w');
        f82 = open('inputss2sgap_'+fid, 'w');
        f83 = open('outputssgap_'+fid, 'w');
        f84 = open('vectorssgap_'+fid,'w')
        f85 = open('indexssgap_'+fid,'w')



        for ai in range(int(num)):
            for aj in range(int(num)):
               zero=0.0
               list_image = [(-1,-1,0),(-1,0,0),(-1,1,0),(0,-1,0),(0,0,0),(0,1,0),(1,-1,0),(1,0,0),(1,1,0)]
               for i in range(len(list_image)):
                   a,b = lattice.get_distance_and_image(atom[ai],atom[aj],list_image[i])
                   if((a<12.0) and (a>0.000000001)):
                      vector=atom[aj]+list_image[i]-atom[ai]
                      cvector=lattice.get_cartesian_coords(vector)
                      rad=cvector[0]*cvector[0]+cvector[1]*cvector[1]+cvector[2]*cvector[2];
                      dvector= np.zeros(4,dtype='float')
                      dvector[0]=1.0/np.sqrt(rad)
                      dvector[1]=cvector[0]/rad
                      dvector[2]=cvector[1]/rad
                      dvector[3]=cvector[2]/rad
                      image=list_image[i] 
                  #    image_idx = IMAGE_IDX[image] * nw * nw
                      compare = 0
                      compare = int(compare) 

                      if((ai<int(num/3)) and (aj<int(num/3)) and (a>6.00) and (flag[ai]==flag[aj])):
                          image_idx2 = i * nw * nw
                          input1,input2=[],[]
                          for ti in range(len(c[ai])):
                              input1.append(c[ai][ti].tolist())
                          for ti in range(len(c[aj])):
                              input2.append(c[aj][ti].tolist())
                          f14.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (dvector[0],dvector[1],dvector[2],dvector[3]))
                          for ti in range(len(input1)):
                              f11.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (input1[ti][0],input1[ti][1],input1[ti][2],input1[ti][3]))
                          for ti in range(len(input2)):
                              f12.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (input2[ti][0],input2[ti][1],input2[ti][2],input2[ti][3]))
                          for wi in range(5):
                              for wj in range(5):
                                  wai=ai*5+wi+1;
                                  waj=aj*5+wj+1;
                                  h_idx2 = image_idx2 + wai-1 + (waj-1)*nw
                                  f15.write("%9d\n" % (h_idx2))
                                  if((image in IMAGE_IDX) and (compare==1)):
                                      image_idx = IMAGE_IDX[image] * nw * nw
                                      h_idx = image_idx + wai-1 + (waj-1)*nw
                                      f13.write("%9.6f\n" % (hoppings[h_idx]))
                                  else:
                                      zero1=0.0
                                      f13.write("%9.6f\n" % (zero1))



                      if((ai<int(num/3)) and (aj>=int(num/3)) and (a>6.00) and (flag[ai]==flag[aj]) ):
                          image_idx2 = i * nw * nw
                          input1,input2=[],[]
                          for ti in range(len(c[ai])):
                              input1.append(c[ai][ti].tolist())
                          for ti in range(len(c[aj])):
                              input2.append(c[aj][ti].tolist())
                   #       zeros4 = np.zeros(4,dtype='float')
                   #       for add_z in range(10):
                   #           input2.append(zeros4)
                          f24.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (dvector[0],dvector[1],dvector[2],dvector[3]))
                          for ti in range(len(input1)):
                              f21.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (input1[ti][0],input1[ti][1],input1[ti][2],input1[ti][3]))
                          for ti in range(len(input2)):
                              f22.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (input2[ti][0],input2[ti][1],input2[ti][2],input2[ti][3]))
                          for wi in range(5):
                              for wj in range(3):
                                  if(wj<3):
                                     wai=ai*5+wi+1;
                                     waj=int(num/3)*5+(aj-int(num/3))*3+wj+1;
                                     h_idx2 = image_idx2 + wai-1 + (waj-1)*nw
                                     f25.write("%9d\n" % (h_idx2))
                                     if((image in IMAGE_IDX) and (compare==1)):
                                          image_idx = IMAGE_IDX[image] * nw * nw
                                          h_idx = image_idx + wai-1 + (waj-1)*nw
                                          f23.write("%9.6f\n" % (hoppings[h_idx]))
                                     else:
                                          zero1=0.0
                                          f23.write("%9.6f\n" % (zero1))


                      if((ai>=int(num/3)) and (aj<int(num/3)) and (a>6.00) and (flag[ai]==flag[aj]) ):
                          image_idx2 = i * nw * nw
                          input1,input2=[],[]
                          for ti in range(len(c[ai])):
                              input1.append(c[ai][ti].tolist())
                          for ti in range(len(c[aj])):
                              input2.append(c[aj][ti].tolist())
                   #       zeros4 = np.zeros(4,dtype='float')
                   #       for add_z in range(10):
                   #           input1.append(zeros4)
                          f34.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (dvector[0],dvector[1],dvector[2],dvector[3]))
                          for ti in range(len(input1)):
                              f31.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (input1[ti][0],input1[ti][1],input1[ti][2],input1[ti][3]))
                          for ti in range(len(input2)):
                              f32.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (input2[ti][0],input2[ti][1],input2[ti][2],input2[ti][3]))
                          for wi in range(3):
                              for wj in range(5):
                                  if(wi<3):
                                     wai=int(num/3)*5+(ai-int(num/3))*3+wi+1;
                                     waj=aj*5+wj+1;
                                     h_idx2 = image_idx2 + wai-1 + (waj-1)*nw
                                     f35.write("%9d\n" % (h_idx2))
                                     if((image in IMAGE_IDX) and (compare==1)):
                                          image_idx = IMAGE_IDX[image] * nw * nw
                                          h_idx = image_idx + wai-1 + (waj-1)*nw
                                          f33.write("%9.6f\n" % (hoppings[h_idx]))
                                     else:
                                          zero1=0.0
                                          f33.write("%9.6f\n" % (zero1))

                      if((ai>=int(num/3)) and (aj>=int(num/3)) and (a>6.00) and (flag[ai]==flag[aj])):
                          image_idx2 = i * nw * nw
                          input1,input2=[],[]
                          for ti in range(len(c[ai])):
                              input1.append(c[ai][ti].tolist())
                          for ti in range(len(c[aj])):
                              input2.append(c[aj][ti].tolist())
                   #       zeros4 = np.zeros(4,dtype='float')
                   #       for add_z in range(10):
                   #           input1.append(zeros4)
                   #       zeros4 = np.zeros(4,dtype='float')
                   #       for add_z in range(10):
                   #           input2.append(zeros4)
                          f44.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (dvector[0],dvector[1],dvector[2],dvector[3]))
                          for ti in range(len(input1)):
                              f41.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (input1[ti][0],input1[ti][1],input1[ti][2],input1[ti][3]))
                          for ti in range(len(input2)):
                              f42.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (input2[ti][0],input2[ti][1],input2[ti][2],input2[ti][3]))
                          for wi in range(3):
                              for wj in range(3):
                                  if((wi<3) and (wj<3)):
                                     wai=int(num/3)*5+(ai-int(num/3))*3+wi+1;
                                     waj=int(num/3)*5+(aj-int(num/3))*3+wj+1;
                                     h_idx2 = image_idx2 + wai-1 + (waj-1)*nw
                                     f45.write("%9d\n" % (h_idx2))
                                     if((image in IMAGE_IDX) and (compare==1)):
                                          image_idx = IMAGE_IDX[image] * nw * nw
                                          h_idx = image_idx + wai-1 + (waj-1)*nw
                                          f43.write("%9.6f\n" % (hoppings[h_idx]))
                                     else:
                                          zero1=0.0
                                          f43.write("%9.6f\n" % (zero1))




                      if((ai<int(num/3)) and (aj<int(num/3)) and (flag[ai]!=flag[aj])):
                          image_idx2 = i * nw * nw
                          input1,input2=[],[]
                          for ti in range(len(c[ai])):
                              input1.append(c[ai][ti].tolist())
                          for ti in range(len(c[aj])):
                              input2.append(c[aj][ti].tolist())
                          f54.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (dvector[0],dvector[1],dvector[2],dvector[3]))
                          for ti in range(len(input1)):
                              f51.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (input1[ti][0],input1[ti][1],input1[ti][2],input1[ti][3]))
                          for ti in range(len(input2)):
                              f52.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (input2[ti][0],input2[ti][1],input2[ti][2],input2[ti][3]))
                          for wi in range(5):
                              for wj in range(5):
                                  wai=ai*5+wi+1;
                                  waj=aj*5+wj+1;
                                  h_idx2 = image_idx2 + wai-1 + (waj-1)*nw
                                  f55.write("%9d\n" % (h_idx2))
                                  if((image in IMAGE_IDX) and (compare==1)):
                                      image_idx = IMAGE_IDX[image] * nw * nw
                                      h_idx = image_idx + wai-1 + (waj-1)*nw
                                      f53.write("%9.6f\n" % (hoppings[h_idx]))
                                  else:
                                      zero1=0.0
                                      f53.write("%9.6f\n" % (zero1))


                      if((ai<int(num/3)) and (aj>=int(num/3)) and (flag[ai]!=flag[aj]) ):
                          image_idx2 = i * nw * nw
                          input1,input2=[],[]
                          for ti in range(len(c[ai])):
                              input1.append(c[ai][ti].tolist())
                          for ti in range(len(c[aj])):
                              input2.append(c[aj][ti].tolist())
                   #       zeros4 = np.zeros(4,dtype='float')
                   #       for add_z in range(10):
                   #           input2.append(zeros4)
                          f64.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (dvector[0],dvector[1],dvector[2],dvector[3]))
                          for ti in range(len(input1)):
                              f61.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (input1[ti][0],input1[ti][1],input1[ti][2],input1[ti][3]))
                          for ti in range(len(input2)):
                              f62.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (input2[ti][0],input2[ti][1],input2[ti][2],input2[ti][3]))
                          for wi in range(5):
                              for wj in range(3):
                                  if(wj<3):
                                     wai=ai*5+wi+1;
                                     waj=int(num/3)*5+(aj-int(num/3))*3+wj+1;
                                     h_idx2 = image_idx2 + wai-1 + (waj-1)*nw
                                     f65.write("%9d\n" % (h_idx2))
                                     if((image in IMAGE_IDX) and (compare==1)):
                                          image_idx = IMAGE_IDX[image] * nw * nw
                                          h_idx = image_idx + wai-1 + (waj-1)*nw
                                          f63.write("%9.6f\n" % (hoppings[h_idx]))
                                     else:
                                          zero1=0.0
                                          f63.write("%9.6f\n" % (zero1))
                                  if(wj>=3):
                                     zero1=0.000
                                     f63.write("%9.6f\n" % (zero1))
                                     h_idx2 = -1
                                     f65.write("%9d\n" % (h_idx2))



                      if((ai>=int(num/3)) and (aj<int(num/3)) and (flag[ai]!=flag[aj]) ):
                          image_idx2 = i * nw * nw
                          input1,input2=[],[]
                          for ti in range(len(c[ai])):
                              input1.append(c[ai][ti].tolist())
                          for ti in range(len(c[aj])):
                              input2.append(c[aj][ti].tolist())
                   #       zeros4 = np.zeros(4,dtype='float')
                   #       for add_z in range(10):
                   #           input1.append(zeros4)
                          f74.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (dvector[0],dvector[1],dvector[2],dvector[3]))
                          for ti in range(len(input1)):
                              f71.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (input1[ti][0],input1[ti][1],input1[ti][2],input1[ti][3]))
                          for ti in range(len(input2)):
                              f72.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (input2[ti][0],input2[ti][1],input2[ti][2],input2[ti][3]))
                          for wi in range(3):
                              for wj in range(5):
                                  if(wi<3):
                                     wai=int(num/3)*5+(ai-int(num/3))*3+wi+1;
                                     waj=aj*5+wj+1;
                                     h_idx2 = image_idx2 + wai-1 + (waj-1)*nw
                                     f75.write("%9d\n" % (h_idx2))
                                     if((image in IMAGE_IDX) and (compare==1)):
                                          image_idx = IMAGE_IDX[image] * nw * nw
                                          h_idx = image_idx + wai-1 + (waj-1)*nw
                                          f73.write("%9.6f\n" % (hoppings[h_idx]))
                                     else:
                                          zero1=0.0
                                          f73.write("%9.6f\n" % (zero1))
                                  if(wi>=3):
                                     zero1=0.000
                                     f73.write("%9.6f\n" % (zero1))
                                     h_idx2 = -1
                                     f75.write("%9d\n" % (h_idx2))



                      if((ai>=int(num/3)) and (aj>=int(num/3)) and (a>6.00) and (flag[ai]!=flag[aj])):
                          image_idx2 = i * nw * nw
                          input1,input2=[],[]
                          for ti in range(len(c[ai])):
                              input1.append(c[ai][ti].tolist())
                          for ti in range(len(c[aj])):
                              input2.append(c[aj][ti].tolist())
                   #       zeros4 = np.zeros(4,dtype='float')
                   #       for add_z in range(10):
                   #           input1.append(zeros4)
                   #       zeros4 = np.zeros(4,dtype='float')
                   #       for add_z in range(10):
                   #           input2.append(zeros4)
                          f84.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (dvector[0],dvector[1],dvector[2],dvector[3]))
                          for ti in range(len(input1)):
                              f81.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (input1[ti][0],input1[ti][1],input1[ti][2],input1[ti][3]))
                          for ti in range(len(input2)):
                              f82.write("%9.6f   %9.6f   %9.6f   %9.6f\n" % (input2[ti][0],input2[ti][1],input2[ti][2],input2[ti][3]))
                          for wi in range(3):
                              for wj in range(3):
                                  if((wi<3) and (wj<3)):
                                     wai=int(num/3)*5+(ai-int(num/3))*3+wi+1;
                                     waj=int(num/3)*5+(aj-int(num/3))*3+wj+1;
                                     h_idx2 = image_idx2 + wai-1 + (waj-1)*nw
                                     f85.write("%9d\n" % (h_idx2))
                                     if((image in IMAGE_IDX) and (compare==1)):
                                          image_idx = IMAGE_IDX[image] * nw * nw
                                          h_idx = image_idx + wai-1 + (waj-1)*nw
                                          f83.write("%9.6f\n" % (hoppings[h_idx]))
                                     else:
                                          zero1=0.0
                                          f83.write("%9.6f\n" % (zero1))
                                  if((wi>=3) or (wj>=3)):
                                     zero1=0.000
                                     f83.write("%9.6f\n" % (zero1))
                                     h_idx2 = -1
                                     f85.write("%9d\n" % (h_idx2))




        f11.close()
        f12.close()
        f13.close()
        f14.close()
        f15.close()

        f21.close()
        f22.close()
        f23.close()
        f24.close()
        f25.close()

        f31.close()
        f32.close()
        f33.close()
        f34.close()
        f35.close()

        f41.close()
        f42.close()
        f43.close()
        f44.close()
        f45.close()

        f51.close()
        f52.close()
        f53.close()
        f54.close()
        f55.close()

        f61.close()
        f62.close()
        f63.close()
        f64.close()
        f65.close()

        f71.close()
        f72.close()
        f73.close()
        f74.close()
        f75.close()

        f81.close()
        f82.close()
        f83.close()
        f84.close()
        f85.close()

    def _get_list1(self, struc, vect, ctr):
        nf=[]
        nv=[]
        nf.append(ctr)
        m=struc.lattice.matrix
        lattice=Lattice(struc.lattice.matrix)
        num=struc.num_sites
        atom=[]
        for i in range(num):
            atom.append(struc.frac_coords[i])
        for i1 in range(len(vect)):
           fv=lattice.get_fractional_coords(vect[i1])
           if(i1<6):
               new_ctr=ctr
               element='S'
           if((i1>=6) and (i1<8)):
               new_ctr=nf[1]
               element='Mo'
           if((i1>=8) and (i1<10)):
               new_ctr=nf[3]
               element='Mo'
           if((i1>=10) and (i1<12)):
               new_ctr=nf[5]
               element='Mo'
           if((i1>=12) and (i1<14)):
               new_ctr=nf[7]
               element='S'
           if((i1>=14) and (i1<16)):
               new_ctr=nf[8]
               element='S'
           if((i1>=16) and (i1<18)):
               new_ctr=nf[8]
               element='S'
           if((i1>=18) and (i1<20)):
               new_ctr=nf[9]
               element='S'
           if((i1>=20) and (i1<22)):
               new_ctr=nf[10]
               element='S'
           if((i1>=22) and (i1<24)):
               new_ctr=nf[10]
               element='S'
           if((i1>=24) and (i1<26)):
               new_ctr=nf[11]
               element='S'
           if((i1>=26) and (i1<28)):
               new_ctr=nf[12]
               element='S'
           if((i1>=28) and (i1<30)):
               new_ctr=nf[12]
               element='S'

           fatom = new_ctr + fv
           t_r=1000.0
           for i2 in range(num):
               if(struc[i2].specie.name == element):
                   dis, image = lattice.get_distance_and_image(atom[i2],fatom)
                   if(dis<t_r):
                     t_r=dis
                     t_i=i2
                     t_image=image
           a=atom[t_i]-t_image
           nf.append(a)
           a=a-ctr
           a=lattice.get_cartesian_coords(a)
           rad=a[0]*a[0]+a[1]*a[1]+a[2]*a[2];
           b= np.zeros(4,dtype='float')
           b[0]=1.0/np.sqrt(rad)
           b[1]=a[0]/rad
           b[2]=a[1]/rad
           b[3]=a[2]/rad
           nv.append(b)
        return nv, nf

    def _get_list2(self, struc, vect, ctr):
        nf=[]
        nv=[]
        nf.append(ctr)
        m=struc.lattice.matrix
        lattice=Lattice(struc.lattice.matrix)
        num=struc.num_sites
        atom=[]
        for i in range(num):
            atom.append(struc.frac_coords[i])
        for i1 in range(len(vect)):
           fv=lattice.get_fractional_coords(vect[i1])
           if(i1==0):
               new_ctr=ctr
               element='S'
           if((i1>=1) and (i1<4)):
               new_ctr=ctr
               element='Mo'
           if((i1>=4) and (i1<8)):
               new_ctr=nf[2]
               element='S'
           if((i1>=8) and (i1<12)):
               new_ctr=nf[3]
               element='S'
           if((i1>=12) and (i1<16)):
               new_ctr=nf[4]
               element='S'
           if((i1>=16) and (i1<17)):
               new_ctr=nf[5]
               element='Mo'
           if((i1>=17) and (i1<19)):
               new_ctr=nf[7]
               element='Mo'
           if((i1>=19) and (i1<20)):
               new_ctr=nf[9]
               element='Mo'
           if((i1>=20) and (i1<22)):
               new_ctr=nf[11]
               element='Mo'
           if((i1>=22) and (i1<23)):
               new_ctr=nf[13]
               element='Mo'
           if((i1>=23) and (i1<25)):
               new_ctr=nf[15]
               element='Mo'
           fatom = new_ctr + fv
           t_r=1000.0
           for i2 in range(num):
               if(struc[i2].specie.name == element):
                   dis, image = lattice.get_distance_and_image(atom[i2],fatom)
                   if(dis<t_r):
                     t_r=dis
                     t_i=i2
                     t_image=image
           a=atom[t_i]-t_image
           nf.append(a)
           a=a-ctr
           a=lattice.get_cartesian_coords(a) 
           rad=a[0]*a[0]+a[1]*a[1]+a[2]*a[2];
           b= np.zeros(4,dtype='float')
           b[0]=1.0/np.sqrt(rad)
           b[1]=a[0]/rad
           b[2]=a[1]/rad
           b[3]=a[2]/rad
           nv.append(b)
        b= np.zeros(4,dtype='float')
        return nv, nf




IMAGE_IDX = {(-2, -1, 0): 0, (-1, -1, 0): 1, (-1, 0, 0): 2, (0, -1, 0): 3, (0, 0, 0): 4, (0, 1, 0): 5, (1, 0, 0): 6,
             ( 1,  1, 0): 7, ( 2,  1, 0): 8}



if __name__ == '__main__':
    didx = '96'
    dataset = CrystalGraphDataset('../dataset/MoS2_{}'.format(didx))
    def process_data(idx):
        dataset[idx]
    N = len(dataset)
    pool = Pool(processes=20)

    for _ in tqdm(pool.imap_unordered(process_data, range(N)), total=N):
        pass