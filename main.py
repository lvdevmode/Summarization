#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Dec 14 17:37:05 2017

@author: lakshay
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from six.moves import xrange
import numpy as np
import h5py
import tensorflow as tf
import time
from datetime import timedelta
import math
import random

import os, sys, pprint, time
import scipy.misc
import numpy as np
import tensorflow as tf
import tensorlayer as tl
from tensorlayer.layers import *
from glob import glob
from random import shuffle
from model import *
from utils import *

import cv2

pp = pprint.PrettyPrinter()

flags = tf.app.flags
flags.DEFINE_integer("epoch", 25, "Epoch to train [25]")
flags.DEFINE_float("learning_rate", 0.0002, "Learning rate of for adam [0.0002]")
flags.DEFINE_float("beta1", 0.5, "Momentum term of adam [0.5]")
flags.DEFINE_integer("train_size", np.inf, "The size of train images [np.inf]")
flags.DEFINE_integer("batch_size", 64, "The number of batch images [64]")
flags.DEFINE_integer("image_size", 64, "The size of image to use (will be center cropped) [108]")
flags.DEFINE_integer("output_size", 64, "The size of the output images to produce [64]")
flags.DEFINE_integer("sample_size", 64, "The number of sample images [64]")
flags.DEFINE_integer("c_dim", 3, "Dimension of image color. [3]")
flags.DEFINE_integer("sample_step", 100, "The interval of generating sample. [500]")
flags.DEFINE_integer("save_step", 100, "The interval of saveing checkpoints. [500]")
flags.DEFINE_string("dataset", "celebA", "The name of dataset [celebA, mnist, lsun]")
flags.DEFINE_string("checkpoint_dir", "checkpoint", "Directory name to save the checkpoints [checkpoint]")
flags.DEFINE_string("sample_dir", "samples", "Directory name to save the image samples [samples]")
flags.DEFINE_boolean("is_train", True, "True for training, False for testing [False]")
flags.DEFINE_boolean("is_crop", False, "True for training, False for testing [False]")
flags.DEFINE_boolean("visualize", False, "True for visualizing, False for nothing [False]")
FLAGS = flags.FLAGS

# Adding Seed so that random initialization is consistent
from numpy.random import seed
seed(1)
from tensorflow import set_random_seed
set_random_seed(2)

def prep_data():
    
    f = h5py.File('features_cifar10sorted.h5', 'r')
    
    train_features = np.array(f['train_images']).astype('float64') 
    train_labels = np.array(f['train_labels'])
    train_files = np.array(f['train_files'])
   
    temp = []
    for i in range(train_labels.shape[0]):
        decoded = train_labels[i].decode('ASCII')
        temp.append(decoded)
    train_labels = np.array(temp)
    
    temp = []
    for i in range(train_files.shape[0]):
        decoded = train_files[i].decode('ASCII')
        temp.append(decoded)
    train_files = np.array(temp)
    
    temp.clear()
        
    return train_features, train_labels, train_files

###### ANN begins.

num_classes = 1

feature_size = 2048

fc_neurons = 1024

batch_size = 64
num_epochs = 24

eval_frequency = 10 # Number of steps between evaluations.

###
        
    
def main(_): 
    pp.pprint(flags.FLAGS.__flags)
    
    tl.files.exists_or_mkdir(FLAGS.checkpoint_dir)
    tl.files.exists_or_mkdir(FLAGS.sample_dir)
    
    with tf.device("/cpu:0"):
        ##========================= DEFINE MODEL ===========================##
        train_features, train_labels, train_files = prep_data()
        
        x_features = tf.placeholder(tf.float64, shape=[FLAGS.batch_size, feature_size])
        real_images =  tf.placeholder(tf.float64, [FLAGS.batch_size, FLAGS.output_size, FLAGS.output_size, FLAGS.c_dim], name='real_images')

        # x --> scorer for training
        net_s, s_logits = sANN_simplified_api(x_features, is_train=True, reuse=False)
        # z --> generator for training
        z = s_logits * x_features
        net_g, g_logits = generator_simplified_api(z, is_train=True, reuse=False)
        # generated fake images --> discriminator
        net_d, d_logits = discriminator_simplified_api(net_g.outputs, is_train=True, reuse=False)
        # real images --> discriminator
        net_d2, d2_logits = discriminator_simplified_api(real_images, is_train=True, reuse=True)
        # sample_z --> generator for evaluation, set is_train to False
        # so that BatchNormLayer behave differently
        net_g2, g2_logits = generator_simplified_api(z, is_train=False, reuse=True)

        ##========================= DEFINE TRAIN OPS =======================##
        # cost for updating discriminator and generator
        # discriminator: real images are labelled as 1
        d_loss_real = tl.cost.sigmoid_cross_entropy(d2_logits, tf.ones_like(d2_logits), name='dreal')
        # discriminator: images from generator (fake) are labelled as 0
        d_loss_fake = tl.cost.sigmoid_cross_entropy(d_logits, tf.zeros_like(d_logits), name='dfake')
        d_loss = d_loss_real + d_loss_fake
        # generator: try to make the the fake images look real (1)
        g_loss = tl.cost.sigmoid_cross_entropy(d_logits, tf.ones_like(d_logits), name='gfake')
        # cost for updating scorer
        
        
        
        
        

        s_vars = tl.layers.get_variables_with_name('sANN', True, True)
        g_vars = tl.layers.get_variables_with_name('generator', True, True)
        d_vars = tl.layers.get_variables_with_name('discriminator', True, True)

        net_s.print_params(True)
        print("---------------")
        net_g.print_params(True)
        print("---------------")
        net_d.print_params(True)

        # optimizers for updating scorer, discriminator and generator
        d_optim = tf.train.AdamOptimizer(FLAGS.learning_rate, beta1=FLAGS.beta1) \
                          .minimize(d_loss, var_list=d_vars)
        g_optim = tf.train.AdamOptimizer(FLAGS.learning_rate, beta1=FLAGS.beta1) \
                          .minimize(g_loss, var_list=g_vars)
        s_optim = tf.train.AdamOptimizer(FLAGS.learning_rate, beta1=FLAGS.beta1) \
                          .minimize(d_loss, var_list=s_vars)
        
    sess = tf.InteractiveSession()
    tl.layers.initialize_global_variables(sess)

    model_dir = "%s_%s_%s" % (FLAGS.dataset, FLAGS.batch_size, FLAGS.output_size)
    save_dir = os.path.join(FLAGS.checkpoint_dir, model_dir)
    tl.files.exists_or_mkdir(FLAGS.sample_dir)
    tl.files.exists_or_mkdir(save_dir)
    # load the latest checkpoints
    net_s_name = os.path.join(save_dir, 'net_s.npz')
    net_g_name = os.path.join(save_dir, 'net_g.npz')
    net_d_name = os.path.join(save_dir, 'net_d.npz')

    #sample_seed = np.random.normal(loc=0.0, scale=1.0, size=(FLAGS.sample_size, z_dim)).astype(np.float64)# sample_seed = np.random.uniform(low=-1, high=1, size=(FLAGS.sample_size, z_dim)).astype(np.float32)

    ##========================= TRAIN MODELS ================================##
    iter_counter = 0
    for epoch in range(FLAGS.epoch):

        ## load image data
        batch_idxs = min(len(train_files), FLAGS.train_size) // FLAGS.batch_size

        for idx in range(batch_idxs):
            batch_files = train_files[idx*FLAGS.batch_size:(idx+1)*FLAGS.batch_size]
            ## get real images
            batch_images = []
            for fl in batch_files:
                image = cv2.imread(fl)
                image = cv2.resize(image, (FLAGS.output_size, FLAGS.output_size), 0, 0, cv2.INTER_CUBIC)
                image = image.astype(np.float64)
                batch_images.append(image)
            batch_images = np.array(batch_images)
            batch_features = train_features[idx*FLAGS.batch_size:(idx+1)*FLAGS.batch_size]
            start_time = time.time()
            # updates the discriminator
            errD, _ = sess.run([d_loss, d_optim], feed_dict={x_features: batch_features, real_images: batch_images })
            # updates the generator, run generator twice to make sure that d_loss does not go to zero (difference from paper)
            for _ in range(2):
                errG, _ = sess.run([g_loss, g_optim], feed_dict={x_features: batch_features})
            # updates the scorer
            errS, _ = sess.run([s_loss, s_optim], feed_dict={x_features: batch_features})
            
            
            
            print("Epoch: [%2d/%2d] [%4d/%4d] time: %4.4f, d_loss: %.8f, g_loss: %.8f. s_loss: %.8f" \
                    % (epoch, FLAGS.epoch, idx, batch_idxs, time.time() - start_time, errD, errG, errS))

            iter_counter += 1
            
            """
            if np.mod(iter_counter, FLAGS.sample_step) == 0:
                # generate and visualize generated images
                img, errD, errG = sess.run([net_g2.outputs, d_loss, g_loss], feed_dict={z : sample_seed, real_images: sample_images})
                tl.visualize.save_images(img, [8, 8], './{}/train_{:02d}_{:04d}.png'.format(FLAGS.sample_dir, epoch, idx))
                print("[Sample] d_loss: %.8f, g_loss: %.8f" % (errD, errG))
            """

            if np.mod(iter_counter, FLAGS.save_step) == 0:
                # save current network parameters
                print("[*] Saving checkpoints...")
                tl.files.save_npz(net_s.all_params, name=net_s_name, sess=sess)
                tl.files.save_npz(net_g.all_params, name=net_g_name, sess=sess)
                tl.files.save_npz(net_d.all_params, name=net_d_name, sess=sess)
                print("[*] Saving checkpoints SUCCESS!")

if __name__ == '__main__':
    tf.app.run()


