import os
from argparse import ArgumentParser

from pytorch_lightning import Trainer
from pytorch_lightning.callbacks import ModelCheckpoint
from pytorch_lightning.loggers import TensorBoardLogger

from imipnet.lightning_module import IMIPLightning

parser = ArgumentParser()
parser = IMIPLightning.add_model_specific_args(parser)
args = parser.parse_args()

imip_module = IMIPLightning(args)
name = imip_module.get_new_run_name()

# TODO: load run dir from params
logger = TensorBoardLogger("./runs", name)

# TODO: load checkpoint dir from params
checkpoint_dir = os.path.join(".", "checkpoints", "simple-conv", name)
os.makedirs(checkpoint_dir, exist_ok=True)
checkpoint_callback = ModelCheckpoint(
    filepath=checkpoint_dir,
    save_last=True,
    verbose=True,
    monitor="eval_true_inliers",
    mode='max',
    period=0  # don't wait for a new epoch to save a better model
)

overfit_val = args.overfit_n

# TODO: load device from params
trainer = Trainer(logger=logger, gpus=[0], val_check_interval=250 if overfit_val == 0 else overfit_val,
                  max_steps=20000 * 5, limit_train_batches=20000 if overfit_val == 0 else 1.0,
                  reload_dataloaders_every_epoch=False,
                  checkpoint_callback=checkpoint_callback)
trainer.fit(imip_module)
