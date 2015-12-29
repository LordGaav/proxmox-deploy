# proxmox-deploy is cli-based deployment tool for Proxmox
#
# Copyright (c) 2015 Nick Douma <n.douma@nekoconeko.nl>
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see http://www.gnu.org/licenses/.

import sys


class Question(object):
    """
    Base Question class, which accepts all answers and stores them as string.
    """
    question_without_default = "{0}: "
    question_with_default = "{0} [{1}]: "

    def __init__(self, question, default=None,
                 _output=sys.stdout, _input=sys.stdin):
        """
        Asks an interactive question and stores the answer. See ask() for the
        workflow.

        Parameters
        ----------
        question: str
            Question to ask the user. Will be formatted and written to output.
        default: any
            Default value. Will be formatted as string and outputted as part of
            the question.
        _output: file
            File to output questions to. sys.stdout by default.
        _input: file
            File to read input from. sys.stdin by default.
        """
        self.question = question
        self.answer = default
        self.input = _input
        self.output = _output

    def _format_question(self):
        if self.answer is not None:
            return self.question_with_default.format(
                self.question,
                self.format_default()
            )
        else:
            return self.question_without_default.format(self.question)

    def _write_question(self):
        self.output.write(self._format_question())

    def _read_answer(self):
        return self.input.readline().strip()

    def ask(self):
        """
        Asks the question to the user. The internal workflow of method calls
        is:
            1. Print question (_write_question and format_default).
            2. Read answer (_read_answer).
            3. If answer was empty and a default was set, use default.
            4. Else, validate the answer (validate).
            5. If valid, format answer (format_answer).
            6. Else, go to 1.

        format_default, format_answer and validate are implemented in the base
        class, but should probably be overridden in subclasses.
        """
        valid = False
        while not valid:
            self._write_question()
            answer = self. _read_answer()
            if answer == "" and self.answer is not None:
                return
            valid = self.validate(answer)
        self.answer = self.format_answer(answer)

    def format_default(self):
        """
        Formats the default value for output to user. In the base class, the
        default will simply be cast to string.
        """
        return str(self.answer)

    def format_answer(self, answer):
        """
        Formats the answer before storing it. In the base class, the answer
        is returned unmodified.
        """
        return answer

    def validate(self, answer):
        """
        Validates the given answer. In the base class, the answer is valid when
        it is not empty.

        This method is responsible for outputting helpful messages if the answer
        is invalid.

        Should return False when invalid.
        """
        return answer != ""


class BooleanQuestion(Question):
    """
    Question class which only accepts boolean answers.
    """
    positive_answers = ["true", "t", "yes", "y"]
    negative_answers = ["false", "f", "no", "n"]

    def validate(self, answer):
        """
        Validates if the given answer is contained in positive_answers or
        negative_answers (case-insensitive).
        """
        if answer.lower() in self.positive_answers:
            answer = True
            return True
        elif answer.lower() in self.negative_answers:
            answer = False
            return True
        else:
            self.output.write("Please answer 'Yes' or 'No'.\n")
            return False

    def format_default(self):
        """
        Formats the default into a user friendly "Yes" or "No".
        """
        if self.answer is True:
            return "Yes"
        else:
            return "No"

    def format_answer(self, answer):
        """
        Converts the given answer into a boolean for storage.
        """
        if answer.lower() in self.positive_answers:
            return True
        else:
            return False


class IntegerQuestion(Question):
    """
    Question class which only accepts integer answers.
    """
    def __init__(self, question, default=None, min_value=None, max_value=None,
                 _output=sys.stdout, _input=sys.stdin):
        super(IntegerQuestion, self).__init__(
            question, default, _output, _input
        )
        self.min_value = min_value
        self.max_value = max_value

    def validate(self, answer):
        """
        Validates the given answer by casting it to an integer. If a min_value
        and/or max_value was supplied to the constructor, also validates the
        answer against that.
        """
        try:
            _answer = int(answer)
        except ValueError:
            self.output.write("Please enter a valid integer.\n")
            return False

        if self.min_value and _answer < self.min_value:
            self.output.write(
                "Please enter a value bigger than {0}.\n"
                .format(str(self.min_value))
            )
            return False

        if self.max_value and _answer > self.max_value:
            self.output.write(
                "Please enter a value smaller than {0}.\n"
                .format(str(self.max_value))
            )
            return False
        return True

    def format_answer(self, answer):
        """
        Casts the answer to an integer.
        """
        return int(answer)
