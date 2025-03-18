.. _newscan-ref-label:

Add a New Scanner
=================

The process of adding a new scanner is relatively simple.  The steps are outlined below.

Create a tool definition file
-----------------------------

This step isn't strictly necessary, but if you want the pipeline to know how to install/uninstall the tool your scanner uses, this is where that is defined.  Tool definition files live in the ``pipeline/tools`` directory.

.. code-block:: console

    pipeline/
    ...
    ├── recon-pipeline.py
    └── tools
        ├── amass.yaml
        ├── aquatone.yaml
        ...

Tool Definition Required Fields
*******************************

Create a ``.yaml`` file with the following fields.

+------------------+------------------+------------------------------------------------------------------------------------------------------------------+----------+
|    Field Name    |       Type       |                                                    Description                                                   | Required |
+==================+==================+==================================================================================================================+==========+
| ``commands``     | Array of strings | Which commands to run to install the tool                                                                        | True     |
+------------------+------------------+------------------------------------------------------------------------------------------------------------------+----------+
| ``dependencies`` | Array of strings | Each dependency must be defined in a separate definition                                                         | False    |
|                  |                  | file, as they'll be installed before the current defintion's tool                                                |          |
+------------------+------------------+------------------------------------------------------------------------------------------------------------------+----------+
| ``environ``      | Dictionary       | Use this if you need to pass information via the                                                                 | False    |
|                  |                  | environment to your tool (amass.yaml has an example)                                                             |          |
+------------------+------------------+------------------------------------------------------------------------------------------------------------------+----------+
| ``shell``        | Boolean          | true means each command in commands will be run via                                                              | False    |
|                  |                  | ``/bin/sh -c`` (see `Popen <https://docs.python.org/3.7/library/subprocess.html#subprocess.Popen>`_'s ``shell``  |          |
|                  |                  | argument for more details)                                                                                       |          |
+------------------+------------------+------------------------------------------------------------------------------------------------------------------+----------+

Useful yaml Helpers
*******************

``pipeline.tools.loader`` defines a few helpful functions to assist with dynamically creating values in yaml files as well as linking user-defined configuration values.

Dynamically creating strings and filesystem paths are handled by the following two functions.

- ``!join`` - join items in an array with a space character
- ``!join_path`` - join items in an array with a ``/`` character

In order to get values out of ``pipeline.recon.config.py``, you'll need to use one of the yaml helpers listed below.

- ``!get_default`` - get a value from the ``pipeline.recon.config.defaults`` dictionary
- ``!get_tool_path`` - get a path value from the ``pipeline.tools.tools`` dictionary

Simple Example Tool Definition
******************************

The example below needs go to be installed prior to being installed itself.  It then grabs the path to the ``go`` binary from ``pipeline.tools.tools`` by using ``!get_tool_path``.  After that, it creates a command using ``!join`` that will look like ``/usr/local/go/bin/go get github.com/tomnomnom/waybackurls``.  This command will be run by the ``install waybackurls`` command (or ``install all``).

.. code-block:: yaml

    dependencies: [go]
    go: &gobin !get_tool_path "{go[path]}"

    commands:
    - !join [*gobin, get github.com/tomnomnom/waybackurls]

If you're looking for a more complex example, check out ``searchsploit.yaml``.

Write Your Scanner Class
------------------------

You can find an abundance of information on how to write your scanner class starting with `Part II <https://epi052.gitlab.io/notes-to-self/blog/2019-09-02-how-to-build-an-automated-recon-pipeline-with-python-and-luigi-part-two/>`_ of the blog posts tied to recon-pipeline's creation.  Because scanner classes are covered in so much detail there, we'll only briefly summarize the steps here:

- Select ``luigi.Task`` or ``luigi.ExternalTask`` as your base class.  Task allows more flexibility while ExternalTask is great for simple scans.
- Implement the ``requires``, ``output``, and either ``run`` (Task) or ``program_args`` (ExternalTask) methods


Add Your Scan to a Wrapper (optional)
-------------------------------------

If you want to run your new scan as part of an existing pipeline, open up ``pipeline.recon.wrappers`` and edit one of the existing wrappers (or add your own) to include your new scan.  You should be able to import your new scan, and then add a ``yield MyNewScan(**args)`` in order to add it to the pipeline.  The only gotcha here is that depending on what arguments your scan takes, you may need to strategically place your scan within the wrapper in order to ensure it doesn't get any arguments that it doesn't expect.

Guidelines for Maintaining and Extending the Project
----------------------------------------------------

1. **Code Readability**: Ensure that the code is easy to read and understand by using meaningful variable names, adding comments where necessary, and following the PEP 8 style guide.

2. **Modularity**: Ensure that the code is modular and follows the single responsibility principle. Each function and class should have a single responsibility and should be as small as possible.

3. **Error Handling**: Ensure that the code has proper error handling to handle unexpected situations gracefully. Use try-except blocks to catch exceptions and provide meaningful error messages.

4. **Testing**: Ensure that the code is thoroughly tested using unit tests and integration tests. Use a testing framework such as `pytest` to write and run the tests.

5. **Documentation**: Ensure that the code is well-documented. Add docstrings to all functions and classes, and update the documentation in the `docs` directory to reflect any changes in the codebase.

6. **Performance**: Ensure that the code is optimized for performance. Use efficient algorithms and data structures, and avoid unnecessary computations.

7. **Security**: Ensure that the code follows best practices for security. Avoid using hard-coded credentials, validate user inputs, and use secure communication protocols.

8. **Extensibility**: Ensure that the code is easy to extend. Use design patterns such as the factory pattern and the strategy pattern to make it easy to add new features and functionality.

9. **Consistency**: Ensure that the code is consistent. Follow a consistent coding style and naming conventions throughout the codebase.

10. **Code Reviews**: Ensure that the code is reviewed by other developers before it is merged into the main branch. Use code review tools such as GitHub pull requests to facilitate the code review process.
