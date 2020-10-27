import os
import numpy as np
import copy
from PIL import Image
import torch
import torchvision.datasets as dset
import torchvision.transforms as transforms
from torch.utils.data.distributed import DistributedSampler
import torchvision.transforms.functional as TF
from .utils import GeneratedDataAugment

def load_dataset(args):
    traindir = os.path.join(args.data_path, 'train')
    valdir = os.path.join(args.data_path, 'val')
    normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                     std=[0.229, 0.224, 0.225])

    train_dataset = dset.ImageFolder(
        traindir,
        transforms.Compose([
            transforms.RandomResizedCrop(224),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            normalize,
        ]))

    train_sampler = DistributedSampler(train_dataset) if args.distributed else None

    train_loader = torch.utils.data.DataLoader(
        train_dataset, batch_size=args.batch_size, shuffle=(train_sampler is None),
        num_workers=args.workers, pin_memory=True, sampler=train_sampler)

    val_dataset = dset.ImageFolder(
        valdir,
        transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            normalize,
        ]))

    val_sampler = DistributedSampler(val_dataset, shuffle=False) if args.distributed else None

    val_loader = torch.utils.data.DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False,
        num_workers=args.workers, pin_memory=True, sampler=val_sampler)

    return train_loader, val_loader

'''
class OODData:
    def __init__(self, args, transform_last=None):
        super(OODData, self).__init__()
        self.eps = args.epsilon
        # self.adv_uni_mixup = args.adv_uni_mixup
        self.transform_last = transform_last
        # self.num_fake = args.num_fake

        # self.datasets = {}
        # self.original_dataset = None
        # for adv_train_folder in args.adv_train_folders:
        #     if adv_train_folder == 'uniform':
        self.normal_data = dset.ImageFolder(
            os.path.join(args.data_path, 'train'),
            transforms.Compose([
                transforms.RandomResizedCrop(224),
                transforms.RandomHorizontalFlip(),
                transforms.ToTensor()
            ]))
        #     else:
        #         self.datasets[adv_train_folder] = dset.ImageFolder(
        #             os.path.join(args.data_path_adv_train, adv_train_folder))
        #         if self.original_dataset is None:
        #             self.original_dataset = copy.deepcopy(self.datasets[adv_train_folder])
        #             for i in range(len(self.original_dataset.samples)):
        #                 self.original_dataset.samples[i] = (self.original_dataset.samples[i][0].replace(
        #                     adv_train_folder, 'origin'), self.original_dataset.samples[i][1])
        #             self.original_dataset.transform = transforms.Compose([
        #                 transforms.Resize(256),
        #                 transforms.CenterCrop(256),
        #             ])
        # self.dataset_keys = list(self.datasets.keys())
        # self.fake_data = dset.ImageFolder(os.path.join(args.data_path_fake, 'train'),
        #     transforms.Compose([
        #         GeneratedDataAugment(args),
        #         transforms.RandomCrop(224),
        #         transforms.RandomHorizontalFlip(),
        #         transforms.ToTensor(),
        #     ]))
        # rng = np.random.RandomState(0)
        # rand_idx = rng.permutation(len(self.fake_data.samples))[:self.num_fake]
        # self.fake_data.samples = [self.fake_data.samples[i] for i in rand_idx]
        # self.fake_data.targets = None

    def __getitem__(self, index):
        img, _ = self.normal_data[index]
        # if attack_method == 'uniform':
        img = torch.empty_like(img).uniform_(-self.eps,
            self.eps).add_(img).clamp_(0, 1)
        # else:
        #     i, j, h, w = transforms.RandomCrop.get_params(
        #         img, output_size=(224, 224))
        #     img = TF.to_tensor(TF.crop(img, i, j, h, w))
        #     if self.adv_uni_mixup > 0:
        #         ori_img, _ = self.original_dataset[data_index]
        #         ori_img = TF.to_tensor(TF.crop(ori_img, i, j, h, w))
        #
        #         adv_perturbations = torch.clamp(img - ori_img, -self.eps, self.eps)
        #         uniform_noise = torch.empty_like(img).uniform_(-self.eps, self.eps)
        #
        #         lam = np.random.beta(self.adv_uni_mixup, self.adv_uni_mixup)
        #         mixup = adv_perturbations * lam + uniform_noise * (1 - lam)
        #         img = mixup.add_(ori_img).clamp_(0, 1)
        img = self.transform_last(img)
        return img

    def __len__(self):
        return len(self.normal_data)
'''

def load_dataset_ft(args):
    normalize = transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                     std=[0.229, 0.224, 0.225])

    train_dataset = dset.ImageFolder(
        os.path.join(args.data_path, 'train'),
        transforms.Compose([
            transforms.RandomResizedCrop(224),
            transforms.RandomHorizontalFlip(),
            transforms.ToTensor(),
            normalize,
        ]))
    train_sampler = DistributedSampler(train_dataset) if args.distributed else None
    train_loader = torch.utils.data.DataLoader(
        train_dataset, batch_size=args.batch_size//2, shuffle=(train_sampler is None),
        num_workers=args.workers, pin_memory=True, sampler=train_sampler)

    # ood_train_dataset = OODData(args, transform_last=normalize)
    # ood_train_sampler = DistributedSampler(ood_train_dataset) if args.distributed else None
    # ood_train_loader = torch.utils.data.DataLoader(
    #     ood_train_dataset, batch_size=args.batch_size//4, shuffle=(ood_train_sampler is None),
    #     num_workers=args.workers, pin_memory=True, sampler=ood_train_sampler)

    val_dataset = dset.ImageFolder(
        os.path.join(args.data_path, 'val'),
        transforms.Compose([
            transforms.Resize(256),
            transforms.CenterCrop(224),
            transforms.ToTensor(),
            normalize,
        ]))
    val_sampler = DistributedSampler(val_dataset, shuffle=False) if args.distributed else None
    val_loader = torch.utils.data.DataLoader(
        val_dataset, batch_size=args.batch_size, shuffle=False,
        num_workers=args.workers, pin_memory=True, sampler=val_sampler)

    rng = np.random.RandomState(0)
    rand_idx = rng.permutation(len(val_dataset.samples))[:1000]
    sub_val_dataset = copy.deepcopy(val_dataset)
    sub_val_dataset.samples = [sub_val_dataset.samples[i] for i in rand_idx]
    sub_val_dataset.targets = [sub_val_dataset.targets[i] for i in rand_idx]

    sub_val_sampler = DistributedSampler(sub_val_dataset, shuffle=False) if args.distributed else None
    sub_val_loader = torch.utils.data.DataLoader(
        sub_val_dataset, batch_size=args.batch_size, shuffle=False,
        num_workers=args.workers, pin_memory=True, sampler=sub_val_sampler)

    # fake_dataset = dset.ImageFolder(
    #     os.path.join(args.data_path_fake, 'val'),
    #     transforms.Compose([
    #         transforms.ToTensor(),
    #         normalize,
    #     ]))
    # fake_sampler = DistributedSampler(fake_dataset, shuffle=False) if args.distributed else None
    # fake_loader = torch.utils.data.DataLoader(
    #     fake_dataset, batch_size=args.batch_size, shuffle=False,
    #     num_workers=args.workers, pin_memory=True, sampler=fake_sampler)

    # adv_loaders = {}
    # for adv_folder in args.adv_val_folders:
    #     adv_dataset2 = dset.ImageFolder(
    #         os.path.join(args.data_path_adv_val, adv_folder),
    #         transforms.Compose([
    #             transforms.ToTensor(),
    #             normalize,
    #         ]))
    #     adv_sampler2 = DistributedSampler(adv_dataset2, shuffle=False) if args.distributed else None
    #     adv_loader2 = torch.utils.data.DataLoader(
    #         adv_dataset2, batch_size=args.batch_size, shuffle=False,
    #         num_workers=args.workers, pin_memory=True, sampler=adv_sampler2)
    #     adv_loaders[adv_folder] = adv_loader2

    return train_loader, val_loader, sub_val_loader#, adv_loaders #fake_loader ood_train_loader
