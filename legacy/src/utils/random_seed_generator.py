#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Random Seed Generator
Monkey 테스트에서 사용할 4자리 랜덤 시드 값을 생성합니다.
"""
import random
import time


class RandomSeedGenerator:
    """4자리 랜덤 시드 생성기"""
    
    @staticmethod
    def generate_seed() -> str:
        """
        4자리 랜덤 시드 생성
        
        Returns:
            str: 4자리 시드 값 (1000-9999)
        """
        # 현재 시간을 기반으로 시드 초기화 (더 랜덤한 결과)
        random.seed(int(time.time() * 1000000) % 1000000)
        
        # 4자리 숫자 생성 (1000-9999)
        seed_value = random.randint(1000, 9999)
        
        return str(seed_value)
    
    @staticmethod
    def generate_seeds(count: int) -> list:
        """
        여러 개의 4자리 랜덤 시드 생성
        
        Args:
            count (int): 생성할 시드 개수
            
        Returns:
            list: 시드 값들의 리스트
        """
        seeds = []
        for _ in range(count):
            # 각 시드마다 약간의 시간 지연으로 더 다양한 값 보장
            time.sleep(0.001)
            seeds.append(RandomSeedGenerator.generate_seed())
        
        return seeds
    
    @staticmethod
    def validate_seed(seed_value: str) -> bool:
        """
        시드 값 유효성 검증
        
        Args:
            seed_value (str): 검증할 시드 값
            
        Returns:
            bool: 유효한 시드인지 여부
        """
        try:
            seed_int = int(seed_value)
            return 1000 <= seed_int <= 9999
        except (ValueError, TypeError):
            return False


# 테스트 코드
if __name__ == "__main__":
    print("=== Random Seed Generator 테스트 ===")
    
    # 단일 시드 생성 테스트
    print("\n1. 단일 시드 생성:")
    for i in range(5):
        seed = RandomSeedGenerator.generate_seed()
        print(f"  생성된 시드 {i+1}: {seed}")
    
    # 다중 시드 생성 테스트
    print("\n2. 다중 시드 생성:")
    seeds = RandomSeedGenerator.generate_seeds(5)
    for i, seed in enumerate(seeds):
        print(f"  시드 {i+1}: {seed}")
    
    # 시드 검증 테스트
    print("\n3. 시드 검증 테스트:")
    test_seeds = ["1234", "9999", "999", "10000", "abcd", "1000"]
    for seed in test_seeds:
        valid = RandomSeedGenerator.validate_seed(seed)
        print(f"  {seed}: {'유효' if valid else '무효'}")
