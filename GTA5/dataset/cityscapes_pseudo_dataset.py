import os
import os.path as osp
import numpy as np
import random
import matplotlib

matplotlib.use('agg')
import matplotlib.pyplot as plt
import collections
import torch
import torchvision
from torch.utils import data
from PIL import Image, ImageFile
from dataset.autoaugment import ImageNetPolicy
import math

ImageFile.LOAD_TRUNCATED_IMAGES = True


class cityscapes_pseudo_DataSet(data.Dataset):
    def __init__(self, data_root, label_root, list_path, max_iters=None, resize_size=(1024, 512), crop_size=(512, 1024),
                 mean=(128, 128, 128), scale=False, mirror=True, ignore_label=255, set='val', autoaug=False,
                 synthia=False, threshold=1.0):
        self.data_root = data_root
        self.label_root = label_root
        self.list_path = list_path
        self.crop_size = crop_size
        self.scale = scale
        self.ignore_label = ignore_label
        self.mean = mean
        self.is_mirror = mirror
        self.resize_size = resize_size
        self.autoaug = autoaug
        self.h = crop_size[0]
        self.w = crop_size[1]
        # self.mean_bgr = np.array([104.00698793, 116.66876762, 122.67891434])
        self.img_ids = [i_id.strip() for i_id in open(list_path)]
        if not max_iters == None:
            self.img_ids = self.img_ids * int(np.ceil(float(max_iters) / len(self.img_ids)))
        self.files = []
        self.set = set

        self.id_to_trainid = {7: 0, 8: 1, 11: 2, 12: 3, 13: 4, 17: 5,
                              19: 6, 20: 7, 21: 8, 22: 9, 23: 10, 24: 11, 25: 12,
                              26: 13, 27: 14, 28: 15, 31: 16, 32: 17, 33: 18}

        for name in self.img_ids:
            img_file = osp.join(self.data_root, "leftImg8bit/%s/%s" % (self.set, name))
            label_file = osp.join(self.label_root, "%s/%s" % (self.set, name))
            if threshold != 1.0:
                label_file = osp.join(self.label_root, "pseudo_%.1f/%s/%s" % (threshold, self.set, name))
            if synthia:
                label_file = osp.join(self.label_root, "pseudo_SYNTHIA/%s/%s" % (self.set, name))
            self.files.append({
                "img": img_file,
                "label": label_file,
                "name": name
            })

    def __len__(self):
        return len(self.files)

    def __getitem__(self, index):
        datafiles = self.files[index]

        image = Image.open(datafiles["img"]).convert('RGB')
        label = Image.open(datafiles["label"])
        name = datafiles["name"]

        # resize
        if self.scale:
            random_scale = 0.8 + random.random() * 0.4
            image_aug1 = image.resize(
                (round(self.resize_size[0] * random_scale), round(self.resize_size[1] * random_scale)), Image.BICUBIC)
            label_aug1 = label.resize(
                (round(self.resize_size[0] * random_scale), round(self.resize_size[1] * random_scale)), Image.NEAREST)
        image = image.resize((self.resize_size[0], self.resize_size[1]), Image.BICUBIC)
        label = label.resize((self.resize_size[0], self.resize_size[1]), Image.NEAREST)

        if self.autoaug:
            policy = ImageNetPolicy()
            image_aug2 = policy(image_aug1)

        image = np.asarray(image, np.float32)
        label = np.asarray(label, np.uint8)
        if self.scale:
            image_aug1 = np.asarray(image_aug1, np.float32)
            image_aug2 = np.asarray(image_aug2, np.float32)
            label_aug1 = np.asarray(label_aug1, np.uint8)
            label_aug2 = np.asarray(label_aug1, np.uint8)

        label_copy = label
        if self.scale:
            label_label_aug1 = label_aug1
            label_label_aug2 = label_aug2

        size = image.shape
        image = image[:, :, ::-1]
        image -= self.mean
        image = image.transpose((2, 0, 1))

        if self.scale:
            image_aug1 = image_aug1[:, :, ::-1]
            image_aug1 -= self.mean
            image_aug1 = image_aug1.transpose((2, 0, 1))
            image_aug2 = image_aug2[:, :, ::-1]
            image_aug2 -= self.mean
            image_aug2 = image_aug2.transpose((2, 0, 1))

        if not self.scale:
            for i in range(10):
                x1 = random.randint(0, image.shape[1] - self.h)
                y1 = random.randint(0, image.shape[2] - self.w)
                tmp_label_copy = label_copy[x1:x1 + self.h, y1:y1 + self.w]
                tmp_image = image[:, x1:x1 + self.h, y1:y1 + self.w]
                u = np.unique(tmp_label_copy)
                if len(u) > 10:
                    break
            image = tmp_image
            label_copy = tmp_label_copy
        else:
            for i in range(10):
                x1 = random.randint(0, image_aug1.shape[1] - self.h)
                y1 = random.randint(0, image_aug1.shape[2] - self.w)
                tmp_label_label_aug1 = label_label_aug1[x1:x1 + self.h, y1:y1 + self.w]
                tmp_image_aug1 = image_aug1[:, x1:x1 + self.h, y1:y1 + self.w]
                tmp_label_label_aug2 = label_label_aug2[x1:x1 + self.h, y1:y1 + self.w]
                tmp_image_aug2 = image_aug2[:, x1:x1 + self.h, y1:y1 + self.w]

                x1_not_scale = math.floor(x1 * ((self.resize_size[1] - self.h) / (image_aug1.shape[1] - self.h)))
                y1_not_scale = math.floor(y1 * ((self.resize_size[0] - self.w) / (image_aug1.shape[2] - self.w)))
                tmp_label_copy = label_copy[x1_not_scale:x1_not_scale + self.h, y1_not_scale:y1_not_scale + self.w]
                tmp_image = image[:, x1_not_scale:x1_not_scale + self.h, y1_not_scale:y1_not_scale + self.w]

                u = np.unique(tmp_label_label_aug1)
                if len(u) > 10:
                    break

            image = tmp_image
            label_copy = tmp_label_copy
            image_aug1 = tmp_image_aug1
            label_label_aug1 = tmp_label_label_aug1
            image_aug2 = tmp_image_aug2
            label_label_aug2 = tmp_label_label_aug2

        if self.is_mirror and random.random() < 0.5:
            image = np.flip(image, axis=2)
            label_copy = np.flip(label_copy, axis=1)

            image_aug1 = np.flip(image_aug1, axis=2)
            label_label_aug1 = np.flip(label_label_aug1, axis=1)
            image_aug2 = np.flip(image_aug2, axis=2)
            label_label_aug2 = np.flip(label_label_aug2, axis=1)

        return image.copy(), label_copy.copy(), np.array(
            size), name, image_aug1.copy(), label_label_aug1.copy(), image_aug2.copy(), label_label_aug2.copy()


if __name__ == '__main__':
    # dst = cityscapes_pseudo_DataSet('./data/Cityscapes/data', './dataset/cityscapes_list/train.txt', mean=(0,0,0), set = 'train', autoaug=True)
    dst = cityscapes_pseudo_DataSet('./data/Cityscapes', './dataset/cityscapes_list/train.txt', mean=(0, 0, 0),
                                    set='train', autoaug=True)
    trainloader = data.DataLoader(dst, batch_size=4)
    for i, data in enumerate(trainloader):
        imgs, _, _, _ = data
        if i == 0:
            img = torchvision.utils.make_grid(imgs).numpy()
            img = np.transpose(img, (1, 2, 0))
            img = img[:, :, ::-1]
            img = Image.fromarray(np.uint8(img))
            img.save('Cityscape_Demo.jpg')
        break
