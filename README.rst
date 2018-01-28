List Lambda functions
=====================

.. image:: https://img.shields.io/badge/Say%20Thanks-!-1EAEDB.svg
   :target: https://saythanks.io/to/ranrib

.. image:: https://github.com/epsagon/list-lambdas/blob/master/list-lambdas.png
   :align: center

(Based on `photo <https://commons.wikimedia.org/wiki/File:AWS_Lambda_logo.svg>`_ by Valve Software / `CC BY-SA 4.0 <https://creativecommons.org/licenses/by-sa/4.0/deed.en>`_)

Motivation
----------
- Enumerate list of Lambda functions from **every region**.
- Detect **"dead"** or unused Lambda functions.


Setup
-----
.. code-block:: bash

    git clone git@github.com:epsagon/list-lambdas.git
    cd list-lambdas/
    pip install -r requirements.txt
    python list_lambdas.py


Example Outputs
---------------

CLI:

.. image:: https://github.com/epsagon/list-lambdas/blob/master/examples/cli.png

CSV file:

.. image:: https://github.com/epsagon/list-lambdas/blob/master/examples/csv.png


Usage
-----

Filter only Lambda functions that has not been active for the past 10 days:

.. code-block:: bash

    python list_lambdas.py --inactive-days-filter 10

Print extended information to the screen (same as in the CSV file):

.. code-block:: bash

    python list_lambdas.py --all

Sort by a chosen column (e.g. by last invocation time):

.. code-block:: bash

    python list_lambdas.py --sort-by last-invocation

Output table (**with extra data**) to a CSV file:

.. code-block:: bash

    python list_lambdas.py --csv lambdas.csv

Provide credentials:

.. code-block:: bash

    python list_lambdas.py --token_key_id <access_key_id> --token_secret <secret_access_key>
