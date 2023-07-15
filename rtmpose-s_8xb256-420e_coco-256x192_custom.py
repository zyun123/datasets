_base_ = ['../../../_base_/default_runtime.py']

# runtime
max_epochs = 420
stage2_num_epochs = 30
base_lr = 4e-3

train_cfg = dict(max_epochs=max_epochs, val_interval=10)# 训练轮数，测试间隔
randomness = dict(seed=21)

# optimizer
optim_wrapper = dict(# 优化器和学习率
    type='OptimWrapper',
    optimizer=dict(type='AdamW', lr=base_lr, weight_decay=0.),
    paramwise_cfg=dict(
        norm_decay_mult=0, bias_decay_mult=0, bypass_duplicate=True))

# learning rate
param_scheduler = [
    dict(# warmup策略
        type='LinearLR',
        start_factor=1.0e-5,
        by_epoch=False,
        begin=0,
        end=1000),
    dict(# scheduler
        # use cosine lr from 210 to 420 epoch
        type='CosineAnnealingLR',
        eta_min=base_lr * 0.05,
        begin=max_epochs // 2,
        end=max_epochs,
        T_max=max_epochs // 2,
        by_epoch=True,
        convert_to_iter_based=True),
]

# automatically scaling LR based on the actual training batch size
auto_scale_lr = dict(base_batch_size=1024)# 根据batch_size自动缩放学习率

# codec settings  定义数据编解码器，用于生成target和对pred进行解码，同时包含了输入图片和输出heatmap尺寸等信息
codec = dict(
    type='SimCCLabel',
    input_size=(1280, 736),
    sigma=(4.9, 5.66),
    simcc_split_ratio=2.0,
    normalize=False,
    use_dark=False)

# model settings
model = dict(
    type='TopdownPoseEstimator',# 模型结构决定了算法流程
    data_preprocessor=dict(
        type='PoseDataPreprocessor',
        mean=[123.675, 116.28, 103.53],
        std=[58.395, 57.12, 57.375],
        bgr_to_rgb=True),
    backbone=dict(# 骨干网络定义
        _scope_='mmdet',
        type='CSPNeXt',
        arch='P5',
        expand_ratio=0.5,
        deepen_factor=0.33,
        widen_factor=0.5,
        out_indices=(4, ),
        channel_attention=True,
        norm_cfg=dict(type='SyncBN'),
        act_cfg=dict(type='SiLU'),
        init_cfg=dict(
            type='Pretrained',# 预训练参数，只加载backbone权重用于迁移学习
            prefix='backbone.',
            checkpoint='pretrained_weights/cspnext-s_udp-aic-coco_210e-256x192-92f5a029_20230130.pth'  # noqa
        )),
    head=dict(# 模型头部
        type='RTMCCHead',
        in_channels=512,
        out_channels=50,
        input_size=codec['input_size'],
        in_featuremap_size=tuple([s // 32 for s in codec['input_size']]),
        simcc_split_ratio=codec['simcc_split_ratio'],
        final_layer_kernel_size=7,
        gau_cfg=dict(
            hidden_dims=256,
            s=128,
            expansion_factor=2,
            dropout_rate=0.,
            drop_path=0.,
            act_fn='SiLU',
            use_rel_bias=False,
            pos_enc=False),
        loss=dict(
            type='KLDiscretLoss',
            use_target_weight=True,
            beta=10.,
            label_softmax=True),
        decoder=codec),# 解码器，将heatmap解码成坐标值
    test_cfg=dict(flip_test=True))# 开启测试时水平翻转集成

# base dataset settings
dataset_type = 'CocoDataset'# 数据集类名
data_mode = 'topdown'# 算法结构类型，用于指定标注信息加载策略
data_root = '/911G/data/temp/20221229新加手托脚托新数据/20230311_最新修改/middle_up_nei_fei/'# 数据存放路径

backend_args = dict(backend='local')# 数据加载后端设置，默认从本地硬盘加载
# backend_args = dict(
#     backend='petrel',
#     path_mapping=dict({
#         f'{data_root}': 's3://openmmlab/datasets/detection/coco/',
#         f'{data_root}': 's3://openmmlab/datasets/detection/coco/'
#     }))

# pipelines
train_pipeline = [# 训练时数据增强
    dict(type='LoadImage', backend_args=backend_args),# 加载图片
    dict(type='GetBBoxCenterScale'),# 根据bbox获取center和scale
    dict(type='RandomFlip', direction='horizontal'),# 生成随机翻转变换矩阵
    # dict(type='RandomFlip', direction='vertical'),# 生成随机翻转变换矩阵
    dict(type='RandomHalfBody'),# 随机半身增强
    dict(
        type='RandomBBoxTransform', scale_factor=[0.6, 1.4], rotate_factor=80), #随机box变换尺寸和随机旋转
    dict(type='TopdownAffine', input_size=codec['input_size']),# 根据变换矩阵更新目标数据
    dict(type='mmdet.YOLOXHSVRandomAug'),
    dict(
        type='Albumentation',
        transforms=[
            dict(type='Blur', p=0.1),
            dict(type='MedianBlur', p=0.1),
            dict(
                type='CoarseDropout',
                max_holes=1,
                max_height=0.4,
                max_width=0.4,
                min_holes=1,
                min_height=0.2,
                min_width=0.2,
                p=1.),
        ]),
    dict(type='GenerateTarget', encoder=codec),# 根据目标数据生成监督信息
    dict(type='PackPoseInputs')# 对target进行打包用于训练
]
val_pipeline = [
    dict(type='LoadImage', backend_args=backend_args),
    dict(type='GetBBoxCenterScale'),
    dict(type='TopdownAffine', input_size=codec['input_size']),
    dict(type='PackPoseInputs')
]

train_pipeline_stage2 = [
    dict(type='LoadImage', backend_args=backend_args),
    dict(type='GetBBoxCenterScale'),
    dict(type='RandomFlip', direction='horizontal'),
    dict(type='RandomHalfBody'),
    dict(
        type='RandomBBoxTransform',
        shift_factor=0.,
        scale_factor=[0.75, 1.25],
        rotate_factor=60),
    dict(type='TopdownAffine', input_size=codec['input_size']),
    dict(type='mmdet.YOLOXHSVRandomAug'),
    dict(
        type='Albumentation',
        transforms=[
            dict(type='Blur', p=0.1),
            dict(type='MedianBlur', p=0.1),
            dict(
                type='CoarseDropout',
                max_holes=1,
                max_height=0.4,
                max_width=0.4,
                min_holes=1,
                min_height=0.2,
                min_width=0.2,
                p=0.5),
        ]),
    dict(type='GenerateTarget', encoder=codec),
    dict(type='PackPoseInputs')
]

# data loaders
train_dataloader = dict(# 训练数据加载
    batch_size=4,
    num_workers=1,
    persistent_workers=True,# 在不活跃时维持进程不终止，避免反复启动进程的开销
    sampler=dict(type='DefaultSampler', shuffle=True),# 采样策略，打乱数据
    dataset=dict(
        type=dataset_type,# 数据集类名
        data_root=data_root,
        data_mode=data_mode,# 算法类型
        ann_file='train_rotate_90.json',# 标注文件路径
        data_prefix=dict(img='train_rotate_90/'),# 图像路径
        pipeline=train_pipeline,# 数据流水线
    ))
val_dataloader = dict(
    batch_size=2,
    num_workers=1,
    persistent_workers=True,
    drop_last=False,
    sampler=dict(type='DefaultSampler', shuffle=False, round_up=False), #不打乱
    dataset=dict(
        type=dataset_type,
        data_root=data_root,
        data_mode=data_mode,
        ann_file='test_rotate_90.json',
        # bbox_file=f'{data_root}person_detection_results/'
        # 'COCO_val2017_detections_AP_H_56_person.json',
        data_prefix=dict(img='test_rotate_90/'),
        test_mode=True,# 测试模式开关
        pipeline=val_pipeline,
    ))
test_dataloader = val_dataloader# 默认情况下不区分验证集和测试集，用户根据需要来自行定义

# hooks
default_hooks = dict(
    checkpoint=dict(save_best='coco/AP', rule='greater', max_keep_ckpts=1))

custom_hooks = [
    dict(
        type='EMAHook',
        ema_type='ExpMomentumEMA',
        momentum=0.0002,
        update_buffers=True,
        priority=49),
    dict(
        type='mmdet.PipelineSwitchHook',
        switch_epoch=max_epochs - stage2_num_epochs,
        switch_pipeline=train_pipeline_stage2)
]

# evaluators
val_evaluator = dict(
    type='CocoMetric',# coco 评测指标
    ann_file=data_root + 'test_rotate_90.json')# 加载评测标注数据
test_evaluator = val_evaluator # 默认情况下不区分验证集和测试集，用户根据需要来自行定义



# visualizer = dict(
#     type='PoseLocalVisualizer', vis_backends=vis_backends, name='visualizer')