# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/CapeOfGoodCode/prepush-ci/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                   |    Stmts |     Miss |   Branch |   BrPart |   Cover |   Missing |
|--------------------------------------- | -------: | -------: | -------: | -------: | ------: | --------: |
| src/prepush\_ci/\_\_init\_\_.py        |        0 |        0 |        0 |        0 |    100% |           |
| src/prepush\_ci/\_\_main\_\_.py        |        2 |        0 |        0 |        0 |    100% |           |
| src/prepush\_ci/checking.py            |       30 |        0 |       10 |        0 |    100% |           |
| src/prepush\_ci/cli.py                 |       61 |        0 |       18 |        0 |    100% |           |
| src/prepush\_ci/commit\_msg\_hook.py   |       58 |        0 |       14 |        0 |    100% |           |
| src/prepush\_ci/core/\_\_init\_\_.py   |        0 |        0 |        0 |        0 |    100% |           |
| src/prepush\_ci/core/commit\_msg.py    |       65 |        0 |       26 |        0 |    100% |           |
| src/prepush\_ci/core/config.py         |       88 |        0 |       34 |        0 |    100% |           |
| src/prepush\_ci/core/config\_source.py |       31 |        0 |        8 |        0 |    100% |           |
| src/prepush\_ci/core/doctor.py         |       92 |        0 |       34 |        0 |    100% |           |
| src/prepush\_ci/core/doctor\_hooks.py  |       86 |        0 |       34 |        0 |    100% |           |
| src/prepush\_ci/core/hook\_managers.py |      185 |        0 |       72 |        0 |    100% |           |
| src/prepush\_ci/core/init.py           |      178 |        0 |       68 |        0 |    100% |           |
| src/prepush\_ci/core/install.py        |       54 |        0 |        8 |        0 |    100% |           |
| src/prepush\_ci/core/pre\_push.py      |       87 |        0 |       30 |        0 |    100% |           |
| src/prepush\_ci/core/preflight.py      |       25 |        0 |        2 |        0 |    100% |           |
| src/prepush\_ci/core/run\_cache.py     |       20 |        0 |        0 |        0 |    100% |           |
| src/prepush\_ci/core/strip.py          |       81 |        0 |       32 |        0 |    100% |           |
| src/prepush\_ci/core/uv\_cache.py      |       32 |        0 |       10 |        0 |    100% |           |
| src/prepush\_ci/core/verify.py         |       45 |        0 |       16 |        0 |    100% |           |
| src/prepush\_ci/doctor\_command.py     |      125 |        5 |       22 |        0 |     97% |37-39, 192-193 |
| src/prepush\_ci/git.py                 |       46 |        3 |       12 |        2 |     91% | 42-43, 77 |
| src/prepush\_ci/init\_command.py       |      189 |        2 |       52 |        1 |     99% |143-\>147, 224-225 |
| src/prepush\_ci/install\_command.py    |      155 |        0 |       50 |        0 |    100% |           |
| src/prepush\_ci/pass\_cache.py         |       34 |        1 |        8 |        1 |     95% |        61 |
| src/prepush\_ci/pre\_push\_hook.py     |       77 |        0 |       24 |        0 |    100% |           |
| src/prepush\_ci/preflight.py           |       32 |        1 |       18 |        1 |     96% |        73 |
| src/prepush\_ci/repo\_config.py        |       17 |        0 |        2 |        0 |    100% |           |
| src/prepush\_ci/run\_command.py        |       29 |        0 |        4 |        0 |    100% |           |
| src/prepush\_ci/strip\_command.py      |      103 |        0 |       38 |        0 |    100% |           |
| src/prepush\_ci/verify\_command.py     |       49 |        1 |       14 |        1 |     97% |        81 |
| **TOTAL**                              | **2076** |   **13** |  **660** |    **6** | **99%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/CapeOfGoodCode/prepush-ci/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/CapeOfGoodCode/prepush-ci/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/CapeOfGoodCode/prepush-ci/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/CapeOfGoodCode/prepush-ci/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2FCapeOfGoodCode%2Fprepush-ci%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/CapeOfGoodCode/prepush-ci/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.