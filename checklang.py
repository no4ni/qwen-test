import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple

class Severity(Enum):
	ERROR = "ERROR"
	WARN = "WARN"

@dataclass
class Issue:
	severity: Severity
	message: str
	suggestion: str

class OntoLinter:
	# Слова и суффиксы, указывающие на процесс
	PROCESS_SUFFIXES = (
		'ание', 'ение', 'ятие', 'тие', 'ование', 'ирование',
		'ство', 'ция', 'ость'
	)
	# Дополнительные процессные слова, если суффикс не сработал
	PROCESS_WORDS_EXTRA = {
		'интуиция', 'логика', 'эмпатия', 'совесть', 'воля',
		'сознание', 'понимание', 'внимание', 'ощущение',
		'восприятие', 'мышление', 'переживание', 'чувствование'
	}

	# Посессивные конструкции (родительный или притяжательные местоимения)
	POSSESSIVE_PATTERNS = [
		r"\bмо[йяё]\s+(\w+)",
		r"\bтво[йяё]\s+(\w+)",
		r"\bего\s+(\w+)",
		r"\bеё\s+(\w+)",
		r"\bее\s+(\w+)",
		r"\bих\s+(\w+)",
		r"\bу\s+меня\s+есть\s+(\w+)",
		r"\bу\s+тебя\s+есть\s+(\w+)",
		r"\bу\s+него\s+есть\s+(\w+)",
		r"\bу\s+неё\s+есть\s+(\w+)",
		r"\bу\s+нее\s+есть\s+(\w+)",
		r"\bу\s+нас\s+есть\s+(\w+)",
		r"\bу\s+них\s+есть\s+(\w+)",
	]

	# Маркеры конкретного времени или события (указывают на инстанс)
	INSTANCE_TIME_MARKERS = [
		'сейчас', 'сегодня', 'вчера', 'завтра', 'утром', 'вечером',
		'только что', 'недавно', 'в тот момент', 'когда', 'пока',
		'во время', 'на встрече', 'на экзамене', 'при переходе',
		'после', 'до', 'в течение', 'в данный момент', 'на этой неделе'
	]

	# Глаголы динамики, указывающие на конкретное проявление (не агентивные)
	DYNAMIC_VERBS = [
		'растёт', 'рассеялось', 'отвлеклось', 'привлекло', 'пришло',
		'ушло', 'изменилось', 'улучшилось', 'ухудшилось', 'появилось',
		'исчезло', 'возникло', 'пропало', 'вернулось', 'сместилось',
		'сконцентрировалось', 'расфокусировалось', 'обострилось',
		'меняется', 'протекает', 'развивается', 'ослабевает', 'усиливается'
	]

	# Агентивные глаголы (процесс не может их выполнять)
	AGENTIVE_VERBS = [
		'подвела', 'подвёл', 'подвело', 'не подвела', 'не подвёл', 'не подвело',
		'помогла', 'помог', 'помогло', 'не помогла', 'не помог', 'не помогло',
		'спасла', 'спас', 'спасло', 'не спасла', 'не спас', 'не спасло',
		'решила', 'решил', 'решило', 'захотела', 'захотел', 'захотело',
		'сделала', 'сделал', 'сделало', 'выполнила', 'выполнил', 'выполнило',
		'сработала', 'сработал', 'сработало', 'не сработала', 'не сработал',
		'обманула', 'обманул', 'обмануло', 'удивила', 'удивил', 'удивило',
		'подсказала', 'подсказал', 'подсказало'
	]

	# Связки, вводящие гипостазирование
	COPULA_PATTERNS = [
		r"\b(\w+)\s+(?:есть|является|суть)\s+(.+)"
	]

	# Бинарные предикаты о процессах (непрерывных)
	BINARY_PROCESS_PATTERNS = [
		(r"\b(сознател[её]н|обладает сознанием|имеет сознание|не обладает сознанием|не имеет сознания)\b", "сознание"),
		(r"\b(понимает|не понимает|осознаёт|не осознаёт)\b", "понимание/осознание"),
		(r"\b(чувствует|не чувствует)\b", "чувствование"),
	]

	# Абсолютные слова
	ABSOLUTE_WORDS = ['всегда', 'никогда', 'везде', 'нигде', 'абсолютно', 'в принципе']

	def __init__(self):
		pass

	def is_process_word(self, word: str) -> bool:
		w = word.lower()
		# Проверяем суффикс
		if w.endswith(self.PROCESS_SUFFIXES):
			# Исключаем некоторые слова, которые не являются процессами (например, "здание")
			# для прототипа оставим просто, добавим словарь исключений при необходимости
			return True
		# Проверяем дополнительный словарь
		if w in self.PROCESS_WORDS_EXTRA:
			return True
		return False

	def has_instance_markers(self, text: str) -> bool:
		for marker in self.INSTANCE_TIME_MARKERS:
			if marker in text.lower():
				return True
		for verb in self.DYNAMIC_VERBS:
			if verb in text.lower():
				return True
		return False

	def has_agentive_verb(self, text: str) -> bool:
		for verb in self.AGENTIVE_VERBS:
			if verb in text.lower():
				return True
		return False

	def is_first_person_present(self, text: str) -> bool:
		# Простая эвристика: есть "я" и глагол в настоящем времени (или прилагательное)
		text_lower = text.lower()
		if 'я ' in text_lower or text_lower.startswith('я '):
			# Проверим, нет ли явных прошедших/будущих времен
			if not re.search(r"\b(был|была|было|буду|будешь|будет|будем|будете|будут)\b", text_lower):
				return True
		return False

	def check_possession_of_type(self, text: str) -> List[Issue]:
		issues = []
		for pattern in self.POSSESSIVE_PATTERNS:
			for match in re.finditer(pattern, text, re.IGNORECASE):
				captured_word = match.group(1)
				if self.is_process_word(captured_word):
					# Проверяем агентность (приоритет)
					if self.has_agentive_verb(text):
						issues.append(Issue(
							severity=Severity.ERROR,
							message=f"Попытка действия процесса. Процесс '{captured_word}' не может быть субъектом.",
							suggestion="Процесс не выполняет действия. Укажите реального субъекта или опишите состояние."
						))
						continue
					# Если есть маркеры инстанса или это первое лицо настоящее, то допустимо
					if self.has_instance_markers(text) or self.is_first_person_present(text):
						# Это описание конкретного проявления/текущего состояния
						continue
					# Иначе - обладание типом
					issues.append(Issue(
						severity=Severity.ERROR,
						message=f"Попытка обладать типом процесса: '{match.group(0)}'",
						suggestion=(
							f"Укажите конкретное проявление (время, динамику) или переформулируйте "
							f"без собственничества, например: 'происходит {captured_word.lower()}'"
						)
					))
		return issues

	def check_copula_hypostasis(self, text: str) -> List[Issue]:
		issues = []
		for pattern in self.COPULA_PATTERNS:
			for match in re.finditer(pattern, text, re.IGNORECASE):
				subject = match.group(1).lower()
				predicate = match.group(2).strip()
				if self.is_process_word(subject):
					issues.append(Issue(
						severity=Severity.WARN,
						message=f"Связка 'быть' с процессом '{subject}': возможно гипостазирование.",
						suggestion=f"Опишите в терминах активности: '{subject} проявляется как ...'"
					))
		return issues

	def check_binary_process_judgments(self, text: str) -> List[Issue]:
		issues = []
		for pattern, process_name in self.BINARY_PROCESS_PATTERNS:
			if re.search(pattern, text, re.IGNORECASE):
				issues.append(Issue(
					severity=Severity.ERROR,
					message=f"Бинарное суждение о континуальном процессе '{process_name}'.",
					suggestion=f"Укажите степень/интенсивность, напр. 'степень {process_name} = 0.7'"
				))
		return issues

	def check_absolutes(self, text: str) -> List[Issue]:
		issues = []
		if any(word in text.lower() for word in self.ABSOLUTE_WORDS):
			# Если это явно личный опыт (1 лицо + прошедшее время или "я" + глагол состояния)
			if self.is_first_person_present(text) or re.search(r"\bя\s+(был|была|было|никогда|всегда|помню|знаю|думаю)\b", text, re.IGNORECASE):
				# Это самоотчёт о личной истории, не пустое
				return issues
			# Иначе - обобщение, выдаём предупреждение
			if not re.search(r"\d|наблюд|эксперимент|данные|пример", text, re.IGNORECASE):
				issues.append(Issue(
					severity=Severity.WARN,
					message="Абсолютное утверждение без эмпирической привязки.",
					suggestion="Добавьте условия проверяемости или ограничьте временные рамки."
				))
		return issues

	def analyze(self, text: str) -> List[Issue]:
		issues = []
		issues.extend(self.check_possession_of_type(text))
		issues.extend(self.check_copula_hypostasis(text))
		issues.extend(self.check_binary_process_judgments(text))
		issues.extend(self.check_absolutes(text))
		return issues

def main():
	linter = OntoLinter()
	print("Онтологический линтер (прототип)")
	print("Вводите предложения по одному. Для выхода введите 'exit' или 'выход'.\n")
	while True:
		try:
			sentence = input("> ").strip()
		except (EOFError, KeyboardInterrupt):
			break
		if sentence.lower() in ('exit', 'выход', 'quit'):
			break
		if not sentence:
			continue
		issues = linter.analyze(sentence)
		if not issues:
			print("  OK")
		else:
			for iss in issues:
				print(f"  [{iss.severity.value}] {iss.message}")
				print(f"	  -> {iss.suggestion}")
		print()

if __name__ == "__main__":
	main()