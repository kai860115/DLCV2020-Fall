import os
import torch
import torch.nn as nn
import torch.nn.functional as F
from model import Model


class Solver(object):
    def __init__(self, trainset_loader, valset_loader, config):
        self.use_cuda = torch.cuda.is_available()
        self.device = torch.device('cuda' if self.use_cuda else 'cpu')
        self.trainset_loader = trainset_loader
        self.valset_loader = valset_loader
        self.epoch = config.epoch
        self.iteration = config.resume_iter
        self.exp_name = config.name
        os.makedirs(config.ckp_dir, exist_ok=True)
        self.ckp_dir = os.path.join(config.ckp_dir, self.exp_name)
        os.makedirs(self.ckp_dir, exist_ok=True)
        self.log_interval = config.log_interval
        self.save_interval = config.save_interval
        self.build_model()

    def build_model(self):
        self.model = Model().to(self.device)
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=1e-5)
        if self.iteration != 0:
            checkpoint_path = os.path.join(self.ckp_dir, 'model.pkl')
            self.load_checkpoint(checkpoint_path, self.iteration)

    def save_checkpoint(self, checkpoint_path, step):
        state = {'state_dict': self.model.state_dict(),
                 'optimizer' : self.optimizer.state_dict()}
        new_checkpoint_path = '{}-{}'.format(checkpoint_path, step+1)
        torch.save(state, new_checkpoint_path)
        print('model saved to %s' % new_checkpoint_path)

    def load_checkpoint(self, checkpoint_path, step):
        new_checkpoint_path = '{}-{}'.format(checkpoint_path, step)
        state = torch.load(new_checkpoint_path)
        self.model.load_state_dict(state['state_dict'])
        self.optimizer.load_state_dict(state['optimizer'])
        print('model loaded from %s' % new_checkpoint_path)
    
    def train(self):
        checkpoint_path = os.path.join(self.ckp_dir, 'model.pkl')
        criterion = nn.CrossEntropyLoss()

        best_acc = 0
        if self.iteration > 0:
            best_acc = self.eval()

        for ep in range(self.epoch):
            self.model.train() 
            for batch_idx, (data, target) in enumerate(self.trainset_loader):
                data, target = data.to(self.device), target.to(self.device)
                self.optimizer.zero_grad()
                _, output = self.model(data)
                loss = criterion(output, target)
                loss.backward()
                self.optimizer.step()

                if self.iteration % self.log_interval == 0 and self.iteration > 0:
                    print('Train Epoch: {} [{}/{} ({:.0f}%)]\tIteration: {}\tLoss: {:.6f}'.format(
                        ep, batch_idx * len(data), len(self.trainset_loader.dataset),
                        100. * batch_idx / len(self.trainset_loader), self.iteration, loss.item()))

                if self.iteration % self.save_interval == 0 and self.iteration > 0:
                    acc = self.eval()
                    if (acc > best_acc):
                        best_acc = acc
                        self.save_checkpoint(checkpoint_path, self.iteration)

                self.iteration += 1
                
        # save the final model
        acc = self.eval()
        if (acc > best_acc):
            best_acc = acc
            self.save_checkpoint(checkpoint_path, self.iteration)


    def eval(self):
        criterion = nn.CrossEntropyLoss()
        self.model.eval()
        test_loss = 0
        correct = 0
        with torch.no_grad():
            for data, target in self.valset_loader:
                data, target = data.to(self.device), target.to(self.device)
                _, output = self.model(data)
                test_loss += criterion(output, target).item()
                pred = output.max(1, keepdim=True)[1]
                correct += pred.eq(target.view_as(pred)).sum().item()

        test_loss /= len(self.valset_loader.dataset)
        print('\nVal set: Average loss: {:.4f}, Accuracy: {}/{} ({:.0f}%)\n'.  format(
            test_loss, correct, len(self.valset_loader.dataset),
            100. * correct / len(self.valset_loader.dataset)))
        return correct / len(self.valset_loader.dataset)