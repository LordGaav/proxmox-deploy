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

from collections import OrderedDict
from contextlib import contextmanager
import sys


class QuestionGroup(OrderedDict):
    """
    A group of Questions, usually about the same subject.
    """
    def __init__(self, questions, *args, **kwargs):
        """
        Parameters
        ----------
        questions: list of tuples
            List of (key, question) tuples. Question order is preserved.
        """
        super(QuestionGroup, self).__init__(*args, **kwargs)
        for key, question in questions:
            self[key] = question

    def ask_all(self, _output=None, _input=None):
        """
        Call the ask() method on all Questions. If nested QuestionGroups are
        encountered, ask_all() on those as well.

        Parameters
        ----------
        _output: file
            Allows for temporarily overriding the output file on each Question.
        _input: file
            Allows for temporarily overriding the input file on each Question.
        """
        for question in self.values():
            if isinstance(question, QuestionGroup):
                question.ask_all()
            else:
                question.ask(_output=_output, _input=_input)

    def flatten_answers(self):
        """
        Flattens all Question answers into a dictionary. Nested QuestionGroups
        are also flattened.
        """
        answers = {}
        for key, question in self.iteritems():
            if isinstance(question, QuestionGroup):
                _answers = question.flatten_answers()
                answers.update(_answers)
            else:
                answers[key] = question.answer
        return answers

    def lookup_answer(self, key):
        return self.flatten_answers()[key]


class Question(object):
    """
    Base Question class, which accepts all answers and stores them as string.
    """
    question_without_default = "{0}: "
    question_with_default = "{0} [{1}]: "

    def __init__(self, question, default=None,
                 _output=sys.stderr, _input=sys.stdin):
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
            File to output questions to. sys.stderr by default.
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

    @contextmanager
    def _override_files(self, _output, _input):
        old_output = self.output
        old_input = self.input
        if _output:
            self.output = _output
        if _input:
            self.input = _input
        yield
        self.output = old_output
        self.input = old_input

    def ask(self, _output=None, _input=None):
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
        with self._override_files(_output, _input):
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
    def __init__(self, question, min_value=None, max_value=None, **kwargs):
        super(IntegerQuestion, self).__init__(question, **kwargs)
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


class EnumQuestion(Question):
    """
    Question class which only accepts answer from a given list.
    """
    def __init__(self, question, valid_answers, default=None, **kwargs):
        super(EnumQuestion, self).__init__(question, default, **kwargs)
        assert len(valid_answers) > 0
        assert default in valid_answers
        self.valid_answers = valid_answers

    def validate(self, answer):
        """
        Validates the given answer by checking it's presence in the
        provided list.
        """
        if answer not in self.valid_answers:
            self.output.write(
                "Please enter one of: {0}\n"
                .format(", ".join(self.valid_answers))
            )
            return False
        return True


class NoAskQuestion(Question):
    """
    Question class which only supplies an answer without asking a Question.
    """
    def __init__(self, question, default, **kwargs):
        super(NoAskQuestion, self).__init__(question, default, **kwargs)

    def ask(self, _output=None, _input=None):
        """
        No questions asked.
        """
        pass

    def format_answer(self, answer):
        """
        Return the answer without any casting or converting.
        """
        return answer
