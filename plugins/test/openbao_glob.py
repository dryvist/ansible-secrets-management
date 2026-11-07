"""Expose standard-library shell glob matching to Ansible selectors."""

from fnmatch import fnmatchcase


class TestModule:
    def tests(self):
        return {"openbao_glob": fnmatchcase}
