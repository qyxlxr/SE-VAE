#!/usr/bin/python
# -*- coding:utf8 -*-
import numpy as np
import math
import os
import time
import json

import torch
import logging


class SimpleLogger(object):
    def __init__(self, f, header='#logger output'):
        dir = os.path.dirname(f)
        self.dir = dir
        self.begin_time_sec = time.time()
        #print('test dir', dir, 'from', f)
        if not os.path.exists(dir):
            os.makedirs(dir)
        with open(f, 'w') as fID:
            fID.write('%s\n'%header)
        self.f = f

    def __call__(self, *args):
        #standard output
        print(*args)
        #log to file
        try:
            with open(self.f, 'a') as fID:
                fID.write('Time_sec = {:.1f} '.format(time.time()-self.begin_time_sec))
                fID.write(' '.join(str(a) for a in args)+'\n')
        except:
            print('Warning: could not log to', self.f)


def normalize_seq(x, dim=0):
    import torch
    eps = 1e-12
    res = (x-torch.mean(x, dim=dim))/torch.sqrt(torch.var(x, dim=dim)).clamp_min(eps)
    # assert torch.mean(torch.mean(res,dim=dim)).norm() <1e-4
    # assert (torch.mean(torch.var(res,dim=dim))-1).norm() <1e-4
    return res


def cal_pearsonr(tensor_seq1, tensor_seq2):
    """

    Args:
        tensor_seq1: shape (len, xxx)
        tensor_seq2: shape (len, xxx)

    Returns:

    """

    if len(tensor_seq1.shape) >= 2:
        pearson_list = [cal_pearsonr(tensor_seq1[:, i], tensor_seq2[:, i]) for i in range(tensor_seq1.shape[1])]
        return np.mean(pearson_list)
    from scipy.stats import pearsonr

    seq1 = tensor_seq1.detach().cpu().numpy()
    seq2 = tensor_seq2.detach().cpu().numpy()
    return pearsonr(seq1, seq2)[0]


def RRSE(y_pred, y_gt):
    assert y_gt.shape == y_pred.shape
    if len(y_gt.shape) == 3:
        return torch.mean(
            torch.stack(
                [RRSE(y_pred[:, i], y_gt[:, i]) for i in range(y_gt.shape[1])]
            )
        )

    elif len(y_gt.shape) == 2:
        # each shape (n_seq, n_outputs)
        se = torch.sum((y_gt - y_pred)**2, dim=0)
        rse = se / torch.sum(
            (y_gt - torch.mean(y_gt, dim=0))**2, dim=0
        )
        return torch.mean(torch.sqrt(rse))
    else:
        raise AttributeError


def softplus(x, threshold=20):
    return torch.where(
        x < threshold, torch.log(1+torch.exp(x)), x
    )


def inverse_softplus(x, threshold=20):
    return torch.where(
        x < threshold, torch.log(torch.exp(x) - torch.ones_like(x)), x
    )


def logsigma2cov(logsigma):
    return torch.diag_embed(softplus(logsigma)**2)


def get_logger(logpath, filepath, package_files=[],
               displaying=True, saving=True, debug=False):
    logger = logging.getLogger()
    if debug:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logger.setLevel(level)
    if saving:
        info_file_handler = logging.FileHandler(logpath, mode='w')
        info_file_handler.setLevel(level)
        logger.addHandler(info_file_handler)
    if displaying:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        logger.addHandler(console_handler)
    logger.info(filepath)

    for f in package_files:
        logger.info(f)
        with open(f, 'r') as package_f:
            logger.info(package_f.read())

    return logger


def cov2logsigma(cov):
    return inverse_softplus(torch.sqrt(cov.diagonal(dim1=-2, dim2=-1)))


def normal_interval(dist, e):
    return dist.loc - e * torch.sqrt(dist.covariance_matrix.diagonal(dim1=-2, dim2=-1)), \
           dist.loc + e * torch.sqrt(dist.covariance_matrix.diagonal(dim1=-2, dim2=-1))



def detect_download(data_urls, base):
    import pandas as pd
    data_paths = []

    def download(url, path):
        """
        数据存储在了阿里云oss上
        Args:
            url:
            path:

        Returns:

        """
        import urllib
        print("Downloading file %s from %s:" % (path, url))
        try:
            urllib.request.urlretrieve(url, filename=os.path.join( path))
            return path
        except Exception as e:
            print("Error occurred when downloading file %s from %s, error message :" % (path, url))
            return None
    for name, url in zip(data_urls['object'], data_urls['url']):
        path = os.path.join(base, name)
        if not os.path.exists(path) and not download(url, path):
            pass
        else:
            data_paths.append(path)
    return data_paths


def merge_first_two_dims(tensor):
    size = tensor.size()
    return tensor.contiguous().reshape(-1, *size[2:])


def split_first_dim(tensor, sizes=None):
    if sizes is None:
        sizes = tensor.size()[0]
    import numpy
    assert type(sizes) is tuple and numpy.prod(sizes) == tensor.size()[0]
    return tensor.contiguous().reshape(*sizes, *tensor.size()[1:])


def training_loss_visualization(base_dir):
    print(base_dir)
    from matplotlib import pyplot as plt
    import re
    import os
    x_dataset_time = []
    y_dataset_train_loss = []
    y_dataset_kl_loss = []
    y_dataset_likelihood_loss = []
    x_dataset_eval_time = []
    y_dataset_eval_loss = []
    y_dataset_eval_train_loss = []
    f = open(os.path.join(base_dir, 'log.out'))
    data = f.readlines()
    f.close()
    for line in data:
        if re.search('train_loss', line):
            pattern = re.compile(r'-?[0-9]\d*\.?\d*')  # 查找数字
            result = pattern.findall(line)
            x_dataset_time.append(float(result[0]))
            y_dataset_train_loss.append(float(result[2]))
            y_dataset_kl_loss.append(float(result[3]))
            y_dataset_likelihood_loss.append(float(result[4]))
        elif re.search('rrse', line):
            y_dataset_eval_train_loss.append(float(result[2]))
            # print(y_dataset_eval_train_loss)
            pattern = re.compile(r'-?[0-9]\d*\.?\d*')  # 查找数字
            result = pattern.findall(line)
            x_dataset_eval_time.append(float(result[0]))
            y_dataset_eval_loss.append(float(result[2]))
    plt.figure()
    plt.plot(x_dataset_time, y_dataset_train_loss, color='red', label="train_loss")
    plt.plot(x_dataset_time, y_dataset_kl_loss, color='blue', label="kl_loss")
    plt.plot(x_dataset_time, y_dataset_likelihood_loss, color='black', label="likelihood_loss")
    plt.xlabel('Time(s)')
    plt.ylabel('loss')
    plt.title('train_loss')
    # plt.xticks(())
    # plt.yticks(())
    plt.legend()
    plt.savefig(os.path.join(base_dir, 'train_loss.png'))

    plt.figure()
    fig, ax = plt.subplots(1, 1)
    plt.plot(x_dataset_eval_time, y_dataset_eval_loss, 'g-', label='eval_loss')
    plt.plot(x_dataset_eval_time, y_dataset_eval_train_loss, 'r-', label='train_loss')
    plt.legend()
    plt.xlabel('Time(s)')
    ax.set_ylabel('eval_loss')
    ax.set_title('eval_loss')
    plt.savefig(os.path.join(base_dir, 'val_loss.png'))
    plt.close()                     #关闭图像，避免出现wraning
    # plt.plot(x_dataset_time,y_dataset_train_loss,color='red',label="train_loss")
    # plt.plot(x_dataset_eval_time,y_dataset_eval_loss,color='black',label="loss")
